import time
import asyncio
import os
import json
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, Query, Request, UploadFile, File
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

# Import refactored core modules
from core.market_data import background_data_fetcher, fetch_yfinance_data, shutdown_event
from core.quant_engine import calculate_asset_allocation, calculate_correlation_matrix, run_montecarlo_sim
from core.llm_agent import generate_llm_insight, generate_morning_brief
from core.yield_curve import get_yield_curve
from core.scenario import run_scenario_analysis
from core.signals import get_multi_timeframe_signals
from core.portfolio_opt import run_efficient_frontier
from core.decision_signal import compute_decision
from core.sector_rotation import get_sector_rotation
from core.asset_rotation import get_theme_rotation, get_domestic_etf_rotation, get_global_etf_rotation
from core.china_macro import get_china_macro
from core.market_breadth import get_market_breadth
from core.fed_prob import get_fed_probability
from core.global_assets import get_global_assets
from core.valuation import get_valuation
from core.data_providers import get_attribution_returns

from core.cache_store import cached, cached_async, ROUTE_TTL, get_cache_stats, invalidate
from core.config import settings
from core.data_quality import score_payload
from core.action_generator import generate_action_recommendation
from core.allocation_model import build_allocation_recommendation
from core.allocation_policy import allocation_policy_to_dict, get_default_allocation_policy
from core.attribution_engine import build_attribution_snapshot
from core.audit_log import get_audit_store
from core.benchmark_book import build_active_risk_snapshot, build_default_benchmark, benchmark_to_dict
from core.compliance_engine import evaluate_pre_trade_compliance
from core.decision_explainer import build_decision_explanation
from core.decision_policy import get_default_decision_policy
from core.decision_ticket import build_decision_ticket
from core.evidence_chain import build_evidence_chain
from core.factor_risk import build_factor_risk_snapshot
from core.portfolio_book import build_portfolio_snapshot, load_portfolio_positions
from core.risk_engine import calculate_portfolio_risk
from core.review_scheduler import build_review_queue, build_review_summary, list_due_reviews
from core.review_scoring import score_review
from core.runtime_diagnostics import build_runtime_diagnostics
from core.scenario_engine import run_portfolio_scenarios
from core.what_if_engine import build_default_risk_reduction_adjustments, run_what_if
from core.alert_rules import get_rules, update_rules, evaluate_all_rules
from core.surprise_index import get_surprise_index
from core.portfolio_manager import get_portfolio_summary
from core.margin_monitor import get_margin_data
from core.dividend_yield import get_dividend_leaders
from core.strategy_lab import get_strategy_dashboard
from core.global_decision_hub import compute_decision_matrix


async def _warm_cache():
    pass
@asynccontextmanager
async def lifespan(app: FastAPI):
    shutdown_event.clear()
    background_task = asyncio.create_task(background_data_fetcher())
    warmup_task = asyncio.create_task(_warm_cache())
    try:
        yield
    finally:
        print("Shutting down background tasks...")
        shutdown_event.set()
        warmup_task.cancel()
        try:
            await asyncio.wait_for(background_task, timeout=5)
        except asyncio.TimeoutError:
            background_task.cancel()
            with suppress(asyncio.CancelledError):
                await background_task


app = FastAPI(title="AlphaCore Quant Data Engine", lifespan=lifespan)


class WhatIfRequest(BaseModel):
    adjustments: dict[str, float] = Field(default_factory=lambda: {
        "SPY": -0.10,
        "GLD": 0.05,
        "CASH": 0.05,
    })


class AllocationModelSimulateRequest(BaseModel):
    market_context: dict = Field(default_factory=dict)
    data_quality_score: int = Field(default=100, ge=0, le=100)
    data_quality_flags: list[str] = Field(default_factory=list)


class CustomShockRequest(BaseModel):
    equity_shock: float = 0.0
    rate_shock: float = 0.0
    vol_shock: float = 0.0
    commodity_shock: float = 0.0


class BlackLittermanRequest(BaseModel):
    views: dict[str, float] = Field(default_factory=dict)
    confidences: dict[str, float] = Field(default_factory=dict)


class RiskParityRequest(BaseModel):
    budgets: dict[str, float] = Field(default_factory=dict)


class CommitCustomDecisionRequest(BaseModel):
    source: str
    portfolio: str | None = None
    views: dict[str, float] = Field(default_factory=dict)
    confidences: dict[str, float] = Field(default_factory=dict)
    shocks: dict[str, float] = Field(default_factory=dict)
    budgets: dict[str, float] = Field(default_factory=dict)


class FrictionRequest(BaseModel):
    target_weights: dict[str, float] = Field(default_factory=dict)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── GZip compression — reduce backtest JSON from 200KB → ~30KB ──
app.add_middleware(GZipMiddleware, minimum_size=1000)

# --- Phase 12: Institutional Security (Rate Limiting) ---
from collections import defaultdict
RATE_LIMIT_DB = defaultdict(list)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    client_ip = request.client.host
    now = time.time()
    RATE_LIMIT_DB[client_ip] = [t for t in RATE_LIMIT_DB[client_ip] if now - t < 60]
    
    if len(RATE_LIMIT_DB[client_ip]) >= settings.MAX_REQUESTS_PER_MINUTE:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too Many Requests. Institutional API rate guard triggered."},
            headers={"Retry-After": "30"},
        )
        
    RATE_LIMIT_DB[client_ip].append(now)
    response = await call_next(request)
    return response

# ── Request timeout guard (cold-start tolerant) ──
_ROUTE_TIMEOUT = {
    "/api/macro/backtest": 60,
    "/api/macro/correlation": 30,
    "/api/macro/montecarlo": 30,
    "/api/macro/efficient_frontier": 30,
    "/api/macro/decision": 45,
    "/api/institutional/decision": 45,
    "/api/macro/global_assets": 30,
    "/api/macro/valuation": 30,
}

@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    timeout = _ROUTE_TIMEOUT.get(request.url.path, 25)
    try:
        return await asyncio.wait_for(call_next(request), timeout=timeout)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"error": f"Request timed out after {timeout}s", "hint": "Check /api/health for source status or retry shortly."},
        )

# --- API Routes ---

@app.get("/api/alerts/rules")
def api_get_rules():
    return {"rules": get_rules()}

class RulesUpdate(BaseModel):
    rules: list[dict]

@app.put("/api/alerts/rules")
def api_update_rules(req: RulesUpdate):
    return {"rules": update_rules(req.rules)}

@app.get("/api/health")
def api_health():
    """System health — data source status + cache metrics."""
    from core.data_providers import get_provider_stats, get_circuit_state
    from core.alert_state import get_active_alerts
    ps = get_provider_stats()
    circuit = get_circuit_state()
    degraded = [k for k, v in ps.items() if v.get("error_rate", 0) > 0.3 or circuit.get(k, {}).get("state") != "closed"]
    diagnostics = build_runtime_diagnostics(settings, cwd=os.getcwd())
    if diagnostics["status"] == "misconfigured":
        status = "misconfigured"
    elif degraded or diagnostics["status"] == "degraded":
        status = "degraded"
    else:
        status = "healthy"
    return {
        "status": status,
        "degraded_sources": degraded,
        "sources": ps,
        "circuit": circuit,
        "cache": get_cache_stats(),
        "diagnostics": diagnostics,
        "rate_limit": {
            "window_sec": 60,
            "max_requests_per_minute": settings.MAX_REQUESTS_PER_MINUTE,
            "tracked_clients": len(RATE_LIMIT_DB),
        },
        "active_alerts": len(get_active_alerts()),
        "routes": list(ROUTE_TTL.keys()),
    }

@app.get("/api/macro/erp")
@cached(ttl=ROUTE_TTL["erp"], key="erp")
def get_erp_data():
    return fetch_yfinance_data("^TNX", "tnx")

@app.get("/api/macro/spread")
@cached(ttl=ROUTE_TTL["spread"], key="spread")
def get_spread_data():
    return fetch_yfinance_data("^VIX", "vix")

async def _build_decision_payload():
    """Aggregate all macro factors into a single decision payload."""
    import asyncio
    
    # Run all blocking IO operations concurrently in threadpool to prevent event loop starvation
    vix_data, tnx_data, yc_data, corr_data = await asyncio.gather(
        asyncio.to_thread(fetch_yfinance_data, "^VIX", "vix"),
        asyncio.to_thread(fetch_yfinance_data, "^TNX", "tnx"),
        asyncio.to_thread(get_yield_curve, 60),
        asyncio.to_thread(calculate_correlation_matrix)
    )

    try:    vix = float(vix_data["data"][-1]) if vix_data.get("data") else 20.0
    except Exception: vix = 20.0
    try:    tnx = float(tnx_data["data"][-1]) if tnx_data.get("data") else 4.0
    except Exception: tnx = 4.0

    spy_tlt_corr = 0.0
    if corr_data.get("matrix"):
        for item in corr_data["matrix"]:
            if (item[0] == 0 and item[1] == 1) or (item[0] == 1 and item[1] == 0):
                spy_tlt_corr = float(item[2]); break

    regime, alloc = "中性震荡 NEUTRAL CHOP", {"spy":60,"tlt":30,"gld":10,"cash":0}
    try:
        from core.backtest import run_backtest
        bt = await asyncio.to_thread(run_backtest)
        s = bt.get("current_state", {})
        regime = s.get("regime", regime)
        alloc = {"spy":s.get("w_spy",60),"tlt":s.get("w_tlt",30),"gld":s.get("w_gld",10),"cash":s.get("w_cash",0)}
    except Exception: pass

    # China macro + valuation for decision engine
    china_data = {}
    pe_pct = 50.0
    try:
        china_data, val_data = await asyncio.gather(
            asyncio.to_thread(get_china_macro, 12),
            asyncio.to_thread(get_valuation)
        )
        for idx in val_data.get("indices", []):
            if "300" in idx.get("name", ""):
                pe_pct = float(idx.get("pe_pct", 50))
                break
    except Exception:
        pass

    result = compute_decision(vix=vix, tnx=tnx, tnx_data=tnx_data, yc_data=yc_data,
                              spy_tlt_corr=spy_tlt_corr, regime=regime,
                              china=china_data, pe_pct=pe_pct)
    result["regime_alloc"] = alloc
    return result

@app.get("/api/macro/decision")
@cached_async(ttl=ROUTE_TTL["decision"], key="decision")
async def api_decision():
    return await _build_decision_payload()

@app.get("/api/macro/yield_curve")
@cached(ttl=ROUTE_TTL["yield_curve"], key="yield_curve")
def api_yield_curve():
    return get_yield_curve(days=120)

@app.get("/api/macro/allocation")
@cached(ttl=ROUTE_TTL["allocation"], key="allocation")
def get_asset_allocation():
    return calculate_asset_allocation()

@app.get("/api/macro/correlation")
@cached(ttl=ROUTE_TTL["correlation"], key="correlation")
def get_correlation_matrix():
    return calculate_correlation_matrix()

@app.get("/api/macro/montecarlo")
@cached(ttl=ROUTE_TTL["montecarlo"], key="montecarlo")
def get_montecarlo_sim():
    return run_montecarlo_sim()

@app.get("/api/macro/efficient_frontier")
@cached_async(ttl=ROUTE_TTL["efficient_frontier"], key="efficient_frontier")
async def api_efficient_frontier():
    return await asyncio.to_thread(run_efficient_frontier)

@app.get("/api/macro/scenario")
@cached_async(ttl=ROUTE_TTL["scenario"], key="scenario")
async def api_scenario():
    return await asyncio.to_thread(run_scenario_analysis)

@app.get("/api/macro/sector_rotation")
@cached(ttl=ROUTE_TTL["sector_rotation"], key="sector_rotation")
def api_sector_rotation():
    return get_sector_rotation(days_back=90)

@app.get("/api/macro/theme_rotation")
@cached(ttl=ROUTE_TTL["theme_rotation"], key="theme_rotation")
def api_theme_rotation():
    return get_theme_rotation()

@app.get("/api/macro/domestic_etf")
@cached(ttl=ROUTE_TTL["domestic_etf"], key="domestic_etf")
def api_domestic_etf():
    return get_domestic_etf_rotation()

@app.get("/api/macro/global_etf")
@cached(ttl=ROUTE_TTL["global_etf"], key="global_etf")
def api_global_etf():
    return get_global_etf_rotation()

@app.get("/api/macro/fed_prob")
@cached(ttl=ROUTE_TTL["fed_prob"], key="fed_prob")
def api_fed_prob():
    return get_fed_probability()

@app.get("/api/macro/global_assets")
@cached(ttl=ROUTE_TTL["global_assets"], key="global_assets_v4")
def api_global_assets():
    return get_global_assets()

@app.get("/api/macro/valuation")
@cached(ttl=ROUTE_TTL["valuation"], key="valuation")
def api_valuation():
    return get_valuation()

@app.get("/api/macro/surprise_index")
@cached(ttl=43200, key="surprise_index")
def api_surprise_index():
    return get_surprise_index(months=36)

@app.get("/api/portfolio/summary")
@cached(ttl=600, key="portfolio_summary")
def api_portfolio():
    return get_portfolio_summary()

@app.get("/api/macro/margin")
@cached(ttl=3600, key="margin_v2")
def api_margin():
    return get_margin_data(days=60)

@app.get("/api/macro/dividend")
@cached(ttl=43200, key="dividend_v7")
def api_dividend():
    return get_dividend_leaders(limit=10)

@app.get("/api/macro/china_macro")
@cached(ttl=ROUTE_TTL["china_macro"], key="china_macro")
def api_china_macro():
    return get_china_macro(months=24)

@app.get("/api/macro/market_breadth")
@cached(ttl=ROUTE_TTL["market_breadth"], key="market_breadth")
def api_market_breadth():
    return get_market_breadth(days=60)

@app.get("/api/macro/signals")
@cached(ttl=ROUTE_TTL["signals"], key="signals")
def api_signals():
    return get_multi_timeframe_signals()

@app.get("/api/macro/ai_insight")
@cached_async(ttl=ROUTE_TTL["ai_insight"], key="ai_insight")
async def get_ai_insight():
    # Phase 22: Async non-blocking thread offloading to prevent event loop lock
    return await asyncio.to_thread(generate_llm_insight)


from core.backtest import run_backtest

@app.get("/api/macro/backtest")
@cached_async(ttl=ROUTE_TTL["backtest"], key="backtest")
async def api_backtest():
    try:
        data = await asyncio.to_thread(run_backtest)
        if "error" in data:
            return JSONResponse(content={"error": data["error"]}, status_code=500)
        return data
    except Exception as e:
        print(f"Backtest error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


def run_historical_replication_analysis_wrapper(portfolio_snapshot: dict, benchmark, portfolio_name: str | None) -> dict:
    try:
        from core.scenario_engine import run_historical_replication_analysis
        from core.portfolio_opt import calculate_risk_parity_allocation
        from core.data_providers import fetch_yfinance_data
        
        try:
            vix_data = fetch_yfinance_data("^VIX", "vix")
            vix = float(vix_data["data"][-1]) if vix_data.get("data") else 20.0
        except Exception:
            vix = 20.0
            
        benchmark_weights = benchmark.positions
        rp_res = calculate_risk_parity_allocation(portfolio_snapshot, benchmark_weights, None)
        risk_parity_weights = rp_res["optimized_weights"]
        
        return run_historical_replication_analysis(
            portfolio_snapshot,
            benchmark_weights,
            risk_parity_weights,
            vix=vix
        )
    except Exception:
        return {}

def _build_institutional_payload(portfolio_name: str | None = None) -> dict:
    policy = get_default_decision_policy()
    portfolio = _build_institutional_portfolio(portfolio_name)
    data_quality = _build_institutional_data_quality(portfolio_name)
    risk = calculate_portfolio_risk(portfolio)
    scenarios = run_portfolio_scenarios(portfolio)
    factor_risk = build_factor_risk_snapshot(portfolio)
    from core.benchmark_book import get_portfolio_benchmark
    benchmark = get_portfolio_benchmark(portfolio_name)
    benchmark_payload = benchmark_to_dict(benchmark)
    active_risk = build_active_risk_snapshot(portfolio, benchmark)
    
    # Run attribution data fetching (synchronously here since it's a huge payload endpoint, 
    # but it uses ThreadPool internally)
    all_symbols = list(set([p["symbol"] for p in portfolio.get("positions", [])] + list(benchmark.positions.keys())))
    returns_t1 = get_attribution_returns(all_symbols, period="T-1")
    attribution = build_attribution_snapshot(
        portfolio, benchmark, period="T-1", 
        asset_returns=returns_t1, benchmark_returns=returns_t1
    )
    
    ticket = build_decision_ticket(data_quality, risk, scenarios, portfolio=portfolio, policy=policy)
    what_if = _build_institutional_what_if(portfolio, build_default_risk_reduction_adjustments(portfolio), portfolio_name)
    action = generate_action_recommendation(ticket, what_if)
    compliance = what_if["compliance"]
    allocation_model = _build_institutional_allocation_model(portfolio=portfolio, data_quality=data_quality)
    evidence_chain = build_evidence_chain(
        decision_ticket=ticket,
        data_quality=data_quality,
        risk=risk,
        scenarios=scenarios,
        factor_risk=factor_risk,
        active_risk=active_risk,
        compliance=compliance,
    )
    explanation = build_decision_explanation(
        decision_ticket=ticket,
        data_quality=data_quality,
        risk=risk,
        scenarios=scenarios,
        portfolio=portfolio,
        what_if=what_if,
        recommended_action=action,
        policy=policy,
    )
    
    # Stage 4 Red-Teaming Simulator Integration
    crisis_path_report = run_historical_replication_analysis_wrapper(portfolio, benchmark, portfolio_name)
    
    return {
        "policy": policy,
        "portfolio": portfolio,
        "data_quality": data_quality,
        "risk": risk,
        "scenarios": scenarios,
        "factor_risk": factor_risk,
        "benchmark": benchmark_payload,
        "active_risk": active_risk,
        "attribution": attribution,
        "compliance": compliance,
        "evidence_chain": evidence_chain,
        "decision_ticket": ticket,
        "what_if": what_if,
        "recommended_action": action,
        "allocation_model": allocation_model,
        "decision_explanation": explanation,
        "historical_crisis_replication": crisis_path_report,
        "audit": {
            "recorded": False,
            "record_endpoint": "/api/institutional/audit/decisions",
            "review_schedule": ticket["review_schedule"],
        },
    }


def _build_institutional_portfolio(portfolio_name: str | None = None) -> dict:
    return build_portfolio_snapshot(load_portfolio_positions(portfolio_name or settings.PORTFOLIO_BOOK_PATH))


def _build_institutional_data_quality(portfolio_name: str | None = None) -> dict:
    target_path = portfolio_name or settings.PORTFOLIO_BOOK_PATH
    has_portfolio_file = False
    if target_path:
        if os.path.exists(target_path):
            has_portfolio_file = True
        else:
            data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))
            if os.path.exists(os.path.join(data_dir, f"{target_path}_portfolio.json")) or os.path.exists(os.path.join(data_dir, f"{target_path}.json")):
                has_portfolio_file = True
                
    source = "portfolio_file" if has_portfolio_file else "sample_portfolio"
    return score_payload(
        source=source,
        updated_secs_ago=0,
        stale_after_sec=3600,
        fallback_used=not has_portfolio_file,
        missing_ratio=0.0,
        anomaly_count=0,
    )


def _build_institutional_market_context() -> dict:
    def collect(name: str, fn, fallback: dict) -> tuple[dict, str, str | None]:
        try:
            payload = fn()
            if not isinstance(payload, dict) or payload.get("error"):
                return fallback, "degraded", str(payload.get("error", "empty payload")) if isinstance(payload, dict) else "invalid payload"
            return payload, "ok", None
        except Exception as exc:
            return fallback, "degraded", str(exc)

    valuation, valuation_status, valuation_error = collect("valuation", get_valuation, {})
    domestic_rotation, domestic_status, domestic_error = collect("domestic_rotation", get_domestic_etf_rotation, {})
    global_rotation, global_status, global_error = collect("global_rotation", get_global_etf_rotation, {})

    source_status = {
        "valuation": valuation_status,
        "domestic_rotation": domestic_status,
        "global_rotation": global_status,
    }
    source_errors = {
        name: error
        for name, error in {
            "valuation": valuation_error,
            "domestic_rotation": domestic_error,
            "global_rotation": global_error,
        }.items()
        if error
    }

    return {
        "macro_decision": {"score": 50, "signal_en": "NEUTRAL"},
        "valuation": valuation,
        "domestic_rotation": domestic_rotation,
        "global_rotation": global_rotation,
        "source_status": source_status,
        "source_errors": source_errors,
    }


def _build_institutional_allocation_model(portfolio: dict | None = None, data_quality: dict | None = None) -> dict:
    portfolio = portfolio or _build_institutional_portfolio()
    data_quality = data_quality or _build_institutional_data_quality()
    try:
        return build_allocation_recommendation(
            portfolio,
            data_quality=data_quality,
            market_context=_build_institutional_market_context(),
        )
    except Exception as exc:
        return _build_allocation_model_degraded_packet(portfolio, data_quality, exc)


def _build_allocation_model_degraded_packet(portfolio: dict, data_quality: dict, exc: Exception) -> dict:
    current_weights = {row["symbol"]: float(row["weight"]) for row in portfolio.get("positions", [])}
    drift = round(1.0 - sum(current_weights.values()), 6)
    if current_weights and drift:
        largest = max(current_weights, key=current_weights.get)
        current_weights[largest] = round(current_weights[largest] + drift, 6)
    return {
        "model_version": "allocation-v1",
        "model_hash": "",
        "status": "observe",
        "degraded": True,
        "degradation_reason": str(exc),
        "policy": allocation_policy_to_dict(get_default_allocation_policy()),
        "current_weights": current_weights,
        "target_weights": current_weights,
        "signals": [],
        "proposed_trades": [],
        "expected_effect": {
            "var_95_delta_pct": 0.0,
            "worst_scenario_delta_pct": 0.0,
            "turnover_pct": 0.0,
            "concentration_delta": 0.0,
        },
        "constraint_result": {
            "status": "block",
            "violations": ["allocation_model_unavailable"],
            "warnings": [],
            "repair_suggestions": ["Review runtime diagnostics before using allocation recommendations."],
        },
        "evidence_chain": [
            {
                "code": "allocation_model_unavailable",
                "message": str(exc),
                "severity": "warning",
            },
            {
                "code": "data_quality_snapshot",
                "message": f"data_quality={data_quality.get('status', 'unknown')}",
                "severity": "info",
            },
        ],
        "review_schedule": ["T+1", "T+5", "T+20"],
    }


def _build_simulated_data_quality(request: AllocationModelSimulateRequest) -> dict:
    return {
        "score": request.data_quality_score,
        "status": "strong" if request.data_quality_score >= 80 else "weak",
        "flags": list(dict.fromkeys(request.data_quality_flags)),
        "source": "simulation",
    }


def _build_institutional_what_if(portfolio: dict, adjustments: dict[str, float], portfolio_name: str | None = None) -> dict:
    what_if = run_what_if(portfolio, adjustments)
    data_quality = _build_institutional_data_quality(portfolio_name)
    current_risk = calculate_portfolio_risk(portfolio)
    what_if["compliance"] = evaluate_pre_trade_compliance(
        portfolio,
        what_if["after"]["portfolio"],
        data_quality=data_quality,
        current_risk=current_risk,
    )
    return what_if


@app.get("/api/institutional/portfolios")
def api_institutional_portfolios():
    from core.portfolio_book import get_available_portfolios
    return {"portfolios": get_available_portfolios()}


@app.get("/api/institutional/portfolio")
@cached(ttl=ROUTE_TTL["institutional_portfolio"], key="institutional_portfolio")
def api_institutional_portfolio(portfolio: str | None = None):
    return _build_institutional_portfolio(portfolio)


@app.get("/api/institutional/data_quality")
@cached(ttl=ROUTE_TTL["institutional_data_quality"], key="institutional_data_quality")
def api_institutional_data_quality(portfolio: str | None = None):
    return _build_institutional_data_quality(portfolio)


@app.get("/api/institutional/risk")
@cached(ttl=ROUTE_TTL["institutional_risk"], key="institutional_risk")
def api_institutional_risk(portfolio: str | None = None):
    portfolio_snapshot = _build_institutional_portfolio(portfolio)
    risk = calculate_portfolio_risk(portfolio_snapshot)
    return risk


@app.get("/api/institutional/scenarios")
@cached(ttl=ROUTE_TTL["institutional_scenarios"], key="institutional_scenarios")
def api_institutional_scenarios(portfolio: str | None = None):
    portfolio_snapshot = _build_institutional_portfolio(portfolio)
    scenarios = run_portfolio_scenarios(portfolio_snapshot)
    return scenarios


@app.get("/api/institutional/scenarios/historical")
def api_historical_crisis_replication(portfolio: str | None = None):
    try:
        from core.scenario_engine import run_historical_replication_analysis
        from core.portfolio_opt import calculate_risk_parity_allocation
        from core.benchmark_book import get_portfolio_benchmark
        from core.data_providers import fetch_yfinance_data
        
        # Volatility calibration from cached VIX index
        try:
            vix_data = fetch_yfinance_data("^VIX", "vix")
            vix = float(vix_data["data"][-1]) if vix_data.get("data") else 20.0
        except Exception:
            vix = 20.0
            
        portfolio_snapshot = _build_institutional_portfolio(portfolio)
        benchmark = get_portfolio_benchmark(portfolio)
        benchmark_weights = benchmark.positions
        
        # Calculate Risk Parity optimal weights
        rp_res = calculate_risk_parity_allocation(portfolio_snapshot, benchmark_weights, None)
        risk_parity_weights = rp_res["optimized_weights"]
        
        res = run_historical_replication_analysis(
            portfolio_snapshot,
            benchmark_weights,
            risk_parity_weights,
            vix=vix
        )
        return res
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/institutional/factors")
@cached(ttl=ROUTE_TTL["institutional_factors"], key="institutional_factors")
def api_institutional_factors(portfolio: str | None = None):
    return build_factor_risk_snapshot(_build_institutional_portfolio(portfolio))


@app.get("/api/institutional/benchmark")
@cached(ttl=ROUTE_TTL["institutional_benchmark"], key="institutional_benchmark")
def api_institutional_benchmark(portfolio: str | None = None):
    from core.benchmark_book import get_portfolio_benchmark
    return benchmark_to_dict(get_portfolio_benchmark(portfolio))


@app.get("/api/institutional/active_risk")
@cached(ttl=ROUTE_TTL["institutional_active_risk"], key="institutional_active_risk")
def api_institutional_active_risk(portfolio: str | None = None):
    from core.benchmark_book import get_portfolio_benchmark
    portfolio_snapshot = _build_institutional_portfolio(portfolio)
    return build_active_risk_snapshot(portfolio_snapshot, get_portfolio_benchmark(portfolio))


@app.get("/api/institutional/attribution")
async def api_institutional_attribution(period: str = "T-1", portfolio: str | None = None):
    from core.benchmark_book import get_portfolio_benchmark
    portfolio_snapshot = _build_institutional_portfolio(portfolio)
    benchmark = get_portfolio_benchmark(portfolio)
    
    # Extract unique symbols from portfolio and benchmark
    port_symbols = [p["symbol"] for p in portfolio_snapshot.get("positions", [])]
    bench_symbols = list(benchmark.positions.keys())
    all_symbols = list(set(port_symbols + bench_symbols))
    
    # Fetch returns concurrently
    import asyncio
    returns = await asyncio.to_thread(get_attribution_returns, all_symbols, period)
    
    return build_attribution_snapshot(
        portfolio_snapshot, benchmark, period=period, 
        asset_returns=returns, benchmark_returns=returns
    )


@app.get("/api/institutional/compliance")
@cached(ttl=ROUTE_TTL["institutional_compliance"], key="institutional_compliance")
def api_institutional_compliance(portfolio: str | None = None):
    portfolio_snapshot = _build_institutional_portfolio(portfolio)
    what_if = _build_institutional_what_if(portfolio_snapshot, build_default_risk_reduction_adjustments(portfolio_snapshot), portfolio)
    return what_if["compliance"]


@app.post("/api/institutional/compliance/check")
def api_institutional_compliance_check(request: WhatIfRequest, portfolio: str | None = None):
    try:
        portfolio_snapshot = _build_institutional_portfolio(portfolio)
        what_if = _build_institutional_what_if(portfolio_snapshot, request.adjustments, portfolio)
        return what_if["compliance"]
    except ValueError as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=400)


@app.get("/api/institutional/decision")
@cached(ttl=ROUTE_TTL["institutional_decision"], key="institutional_decision")
def api_institutional_decision(portfolio: str | None = None):
    return _build_institutional_payload(portfolio)


@app.post("/api/institutional/import_tdx")
async def api_import_tdx(file: UploadFile = File(...)):
    import shutil
    import tempfile
    import os
    
    fd, temp_path = tempfile.mkstemp(suffix=".txt")
    try:
        from core.tdx_parser import import_tdx_to_portfolio
        
        # Save uploaded file to a temporary file
        with os.fdopen(fd, 'wb') as f:
            shutil.copyfileobj(file.file, f)
            
        import_tdx_to_portfolio(temp_path, settings.PORTFOLIO_BOOK_PATH)
        
        # Invalidate decision cache
        invalidate("institutional_decision")
        return {"status": "success", "message": "TDX portfolio imported"}
    except Exception as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=400)
    finally:
        # Clean up temp file safely
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


@app.get("/api/institutional/import_tdx")
def api_import_tdx_get():
    # just an alias if GET is used by mistake
    return JSONResponse(content={"error": "Use POST"}, status_code=405)


@app.get("/api/institutional/ai_compliance_review")
@cached(ttl=ROUTE_TTL["institutional_compliance"], key="ai_compliance_review")
def api_institutional_ai_compliance_review():
    try:
        from core.llm_agent import generate_portfolio_compliance_insight, generate_red_team_advisory
        # Grab the latest decision payload to get risk numbers
        payload = _build_institutional_payload()
        comp_status = payload.get("compliance", {}).get("status", "unknown")
        active_risk = payload.get("active_risk", {})
        tracking_error = active_risk.get("tracking_error_proxy_pct", 0.0)
        
        factor_risk = payload.get("factor_risk", {})
        top_factor_name = "N/A"
        if "top_factor" in factor_risk and factor_risk["top_factor"]:
            top_factor_name = factor_risk["top_factor"].get("factor_name", "N/A")
            
        portfolio = payload.get("portfolio", {})
        concentration = portfolio.get("concentration_level", "low")
        var_95 = payload.get("risk", {}).get("var_95_pct", 0.0)
        
        # Scenarios
        worst_scenario = payload.get("scenarios", {}).get("worst_scenario", {})
        worst_scenario_name = worst_scenario.get("name_zh", "未知冲击")
        worst_loss = worst_scenario.get("portfolio_loss_pct", 0.0)
        
        cro_review = generate_portfolio_compliance_insight(comp_status, tracking_error, var_95, top_factor_name, concentration)
        red_team = generate_red_team_advisory(comp_status, tracking_error, var_95, top_factor_name, concentration, worst_scenario_name, worst_loss)
        
        return {
            "insight": cro_review.get("insight", ""),
            "red_team_advisory": red_team.get("insight", "")
        }
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(exc)}, status_code=500)



@app.get("/api/institutional/portfolio_raw")
def api_institutional_portfolio_raw(portfolio: str | None = None):
    try:
        from core.portfolio_book import load_portfolio_positions, build_portfolio_snapshot
        from core.risk_engine import calculate_portfolio_risk
        
        positions = load_portfolio_positions(portfolio)
        snapshot = build_portfolio_snapshot(positions)
        risk = calculate_portfolio_risk(snapshot)
        
        liquidity = risk.get("liquidity_metrics", {})
        dtl_dict = liquidity.get("days_to_liquidate", {})
        adv_dict = liquidity.get("adv_20d", {})
        
        raw_positions = []
        mctr_dict = risk.get("mctr", {})
        actr_dict = risk.get("actr", {})
        norm_dict = risk.get("normalized_risk_contribution", {})
        
        for pos in snapshot["positions"]:
            symbol = pos["symbol"]
            pos["days_to_liquidate"] = dtl_dict.get(symbol, 0.0)
            pos["adv_20d"] = adv_dict.get(symbol, 0.0)
            pos["mctr"] = mctr_dict.get(symbol, 0.0)
            pos["actr"] = actr_dict.get(symbol, 0.0)
            pos["normalized_risk_contribution"] = norm_dict.get(symbol, 0.0)
            raw_positions.append(pos)
            
        return {"positions": raw_positions}
    except Exception as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=500)


@app.get("/api/institutional/simulation/scenarios")
async def api_simulation_scenarios():
    try:
        from core.scenario_engine import SCENARIO_SHOCKS
        return {"scenarios": SCENARIO_SHOCKS}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/institutional/scenarios/custom")
def api_custom_scenario_shock(request: CustomShockRequest, portfolio: str | None = None):
    try:
        from core.scenario_engine import run_custom_shock_analysis
        portfolio_snapshot = _build_institutional_portfolio(portfolio)
        res = run_custom_shock_analysis(portfolio_snapshot, request.dict())
        return res
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/institutional/portfolio_opt/black_litterman")
def api_black_litterman_optimization(request: BlackLittermanRequest, portfolio: str | None = None):
    try:
        from core.portfolio_opt import calculate_black_litterman
        from core.benchmark_book import get_portfolio_benchmark
        
        portfolio_snapshot = _build_institutional_portfolio(portfolio)
        benchmark = get_portfolio_benchmark(portfolio)
        benchmark_weights = benchmark.positions
        
        res = calculate_black_litterman(
            portfolio_snapshot,
            benchmark_weights,
            request.views,
            request.confidences
        )
        return res
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/institutional/portfolio_opt/risk_parity")
def api_risk_parity_optimization(request: RiskParityRequest, portfolio: str | None = None):
    try:
        from core.portfolio_opt import calculate_risk_parity_allocation
        from core.benchmark_book import get_portfolio_benchmark
        
        portfolio_snapshot = _build_institutional_portfolio(portfolio)
        benchmark = get_portfolio_benchmark(portfolio)
        benchmark_weights = benchmark.positions
        
        res = calculate_risk_parity_allocation(
            portfolio_snapshot,
            benchmark_weights,
            request.budgets
        )
        return res
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.post("/api/institutional/audit/commit_custom")
def api_commit_custom_decision(request: CommitCustomDecisionRequest):
    try:
        portfolio_snapshot = _build_institutional_portfolio(request.portfolio)
        data_quality = _build_institutional_data_quality(request.portfolio)
        policy = get_default_decision_policy()
        
        risk = calculate_portfolio_risk(portfolio_snapshot)
        scenarios = run_portfolio_scenarios(portfolio_snapshot)
        
        if request.source == "bayesian_rebalance":
            from core.portfolio_opt import calculate_black_litterman
            from core.benchmark_book import get_portfolio_benchmark
            bench = get_portfolio_benchmark(request.portfolio)
            bl_res = calculate_black_litterman(portfolio_snapshot, bench.positions, request.views, request.confidences)
            
            simulated_positions = []
            for p in portfolio_snapshot.get("positions", []):
                sym = p["symbol"]
                new_w = bl_res["optimized_weights"].get(sym, p["weight"])
                new_mv = new_w * portfolio_snapshot["total_market_value"]
                import copy
                cloned = copy.deepcopy(p)
                cloned["weight"] = new_w
                cloned["market_value"] = round(new_mv, 2)
                simulated_positions.append(cloned)
                
            simulated_portfolio = copy.deepcopy(portfolio_snapshot)
            simulated_portfolio["positions"] = simulated_positions
            
            compliance = evaluate_pre_trade_compliance(
                portfolio_snapshot,
                simulated_portfolio,
                data_quality=data_quality,
                current_risk=risk
            )
            explanation = build_decision_explanation(
                decision_ticket={"score": 85, "decision_status": "observe"},
                data_quality=data_quality,
                risk=risk,
                scenarios=scenarios,
                portfolio=portfolio_snapshot,
                what_if={"compliance": compliance, "before": {"portfolio": portfolio_snapshot}, "after": {"portfolio": simulated_portfolio}},
                recommended_action={"status": "executed", "action_en": "Rebalance via Bayesian Opt", "action_zh": "执行贝叶斯再平衡"},
                policy=policy
            )
        elif request.source == "risk_parity_rebalance":
            from core.portfolio_opt import calculate_risk_parity_allocation
            from core.benchmark_book import get_portfolio_benchmark
            bench = get_portfolio_benchmark(request.portfolio)
            rp_res = calculate_risk_parity_allocation(portfolio_snapshot, bench.positions, request.budgets)
            
            simulated_positions = []
            for p in portfolio_snapshot.get("positions", []):
                sym = p["symbol"]
                new_w = rp_res["optimized_weights"].get(sym, p["weight"])
                new_mv = new_w * portfolio_snapshot["total_market_value"]
                import copy
                cloned = copy.deepcopy(p)
                cloned["weight"] = new_w
                cloned["market_value"] = round(new_mv, 2)
                simulated_positions.append(cloned)
                
            simulated_portfolio = copy.deepcopy(portfolio_snapshot)
            simulated_portfolio["positions"] = simulated_positions
            
            compliance = evaluate_pre_trade_compliance(
                portfolio_snapshot,
                simulated_portfolio,
                data_quality=data_quality,
                current_risk=risk
            )
            explanation = build_decision_explanation(
                decision_ticket={"score": 92, "decision_status": "pass"},
                data_quality=data_quality,
                risk=risk,
                scenarios=scenarios,
                portfolio=portfolio_snapshot,
                what_if={"compliance": compliance, "before": {"portfolio": portfolio_snapshot}, "after": {"portfolio": simulated_portfolio}},
                recommended_action={"status": "executed", "action_en": "Rebalance via Risk Parity", "action_zh": "执行风险平价再平衡"},
                policy=policy
            )
        else:
            from core.scenario_engine import run_custom_shock_analysis
            shock_res = run_custom_shock_analysis(portfolio_snapshot, request.shocks)
            
            compliance = {
                "status": "warning" if shock_res["status"] == "yellow" else "block" if shock_res["status"] == "red" else "pass",
                "violations": ["custom_black_swan_limit_exceeded"] if shock_res["status"] == "red" else [],
                "warnings": ["custom_black_swan_alert"] if shock_res["status"] == "yellow" else [],
                "repair_suggestions": ["Rebalance portfolio or purchase options to hedge risk."] if shock_res["status"] != "green" else []
            }
            explanation = {
                "verdict_zh": f"自定义因子压测触发评估。预估总损失: {shock_res['custom_loss_pct']}%",
                "verdict_en": f"Custom factor stress test triggered. Estimated portfolio loss: {shock_res['custom_loss_pct']}%",
                "primary_driver": {"code": "custom_stress_testing", "desc_zh": "自定义因子压测", "desc_en": "Custom Shock Sandbox"}
            }
            
        from uuid import uuid4
        ticket = {
            "ticket_id": f"dt_{uuid4().hex[:12]}",
            "score": 75 if compliance["status"] != "pass" else 90,
            "decision_status": "block" if compliance["status"] == "block" else "warning" if compliance["status"] == "warning" else "pass",
            "policy_version": policy.get("version", "v1"),
            "review_schedule": ["T+1", "T+5", "T+20"]
        }
        
        payload = {
            "policy": policy,
            "portfolio": portfolio_snapshot,
            "data_quality": data_quality,
            "risk": risk,
            "scenarios": scenarios,
            "compliance": compliance,
            "decision_ticket": ticket,
            "decision_explanation": explanation,
            "recommended_action": {"status": "executed", "action_en": "Custom Sandbox Archiving", "action_zh": "自定义沙盘归档存证"},
            "views": request.views,
            "confidences": request.confidences,
            "shocks": request.shocks,
            "budgets": request.budgets
        }
        
        record = get_audit_store().record_decision(payload, source=request.source)
        
        invalidate("institutional_audit_log")
        invalidate("institutional_reviews_due")
        invalidate("institutional_reviews_summary")
        return {"status": "success", "ticket_id": record["ticket_id"], "record": {k:v for k,v in record.items() if k != "payload"}}
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/institutional/strategies")
def api_institutional_strategies():
    return get_strategy_dashboard()


@app.get("/api/institutional/qmt_status")
def api_institutional_qmt_status(portfolio: str | None = None):
    """Retrieve QMT Gateway heartbeats and check for portfolio holdings consistency drift."""
    try:
        from core.runtime_diagnostics import check_qmt_portfolio_drift
        
        # 1. Load Heartbeat status
        qmt_status = "OFFLINE"
        heartbeat_data = None
        status_file = os.path.join(os.path.dirname(__file__), "qmt_heartbeat.json")
        if os.path.exists(status_file):
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    heartbeat_data = json.load(f)
                if time.time() - heartbeat_data.get("timestamp", 0) < 30.0:
                    qmt_status = "ONLINE"
            except Exception:
                pass
                
        # 2. Get local positions
        portfolio_snapshot = _build_institutional_portfolio(portfolio)
        positions = portfolio_snapshot.get("positions", [])
        
        # 3. Check for consistency drift
        drift_report = check_qmt_portfolio_drift(positions)
        
        return {
            "status": qmt_status,
            "heartbeat": heartbeat_data,
            "drift_report": drift_report
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/institutional/decision_hub")
def api_institutional_decision_hub():
    """L1 to L5 Global Decision Matrix Funnel"""
    return compute_decision_matrix()

@app.get("/api/institutional/policy")
@cached(ttl=ROUTE_TTL["institutional_policy"], key="institutional_policy")
def api_institutional_policy():
    return get_default_decision_policy()


@app.get("/api/institutional/aiae_backtest")
async def api_aiae_backtest():
    try:
        from core.backtest_scientific import run_scientific_backtest
        # Run in threadpool since it does blocking HTTP requests and heavy pandas calculations
        res = await asyncio.to_thread(run_scientific_backtest)
        if "error" in res:
            return JSONResponse(status_code=500, content=res)
        return res
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})



@app.get("/api/institutional/allocation_model")
@cached(ttl=ROUTE_TTL["institutional_allocation_model"], key="institutional_allocation_model")
def api_institutional_allocation_model(portfolio: str | None = None):
    portfolio_snapshot = _build_institutional_portfolio(portfolio)
    data_quality = _build_institutional_data_quality(portfolio)
    return _build_institutional_allocation_model(portfolio_snapshot, data_quality)


@app.get("/api/institutional/allocation_model/policy")
@cached(ttl=ROUTE_TTL["institutional_allocation_model_policy"], key="institutional_allocation_model_policy")
def api_institutional_allocation_model_policy():
    return allocation_policy_to_dict(get_default_allocation_policy())


@app.post("/api/institutional/allocation_model/simulate")
def api_institutional_allocation_model_simulate(request: AllocationModelSimulateRequest, portfolio: str | None = None):
    portfolio_snapshot = _build_institutional_portfolio(portfolio)
    return build_allocation_recommendation(
        portfolio_snapshot,
        data_quality=_build_simulated_data_quality(request),
        market_context=request.market_context,
    )


@app.post("/api/institutional/allocation_model/audit")
def api_record_institutional_allocation_model(portfolio: str | None = None):
    payload = _build_institutional_payload(portfolio)
    record = get_audit_store().record_decision(payload, source="allocation_model_api")
    invalidate("institutional_audit_log")
    invalidate("institutional_reviews_due")
    invalidate("institutional_reviews_summary")
    invalidate("institutional_review_scores")
    invalidate("institutional_review_outcomes")
    return {
        "record": {k: v for k, v in record.items() if k != "payload"},
        "payload": payload,
    }


@app.get("/api/institutional/what_if")
@cached(ttl=ROUTE_TTL["institutional_what_if"], key="institutional_what_if")
def api_institutional_what_if_default(portfolio: str | None = None):
    portfolio_snapshot = _build_institutional_portfolio(portfolio)
    return _build_institutional_what_if(portfolio_snapshot, build_default_risk_reduction_adjustments(portfolio_snapshot), portfolio)


@app.post("/api/institutional/what_if")
def api_institutional_what_if(request: WhatIfRequest, portfolio: str | None = None):
    try:
        portfolio_snapshot = _build_institutional_portfolio(portfolio)
        return _build_institutional_what_if(portfolio_snapshot, request.adjustments, portfolio)
    except ValueError as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=400)


@app.post("/api/institutional/sandbox/friction")
def api_institutional_sandbox_friction(request: FrictionRequest, portfolio: str | None = None):
    try:
        from core.trade_constraints import calculate_ex_ante_transaction_costs
        portfolio_snapshot = _build_institutional_portfolio(portfolio)
        total_market_value = float(portfolio_snapshot["total_market_value"])
        current_weights = {p["symbol"]: float(p["weight"]) for p in portfolio_snapshot["positions"]}
        
        result = calculate_ex_ante_transaction_costs(
            total_market_value=total_market_value,
            current_weights=current_weights,
            target_weights=request.target_weights,
        )
        return result
    except ValueError as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=400)



@app.get("/api/institutional/action")
@cached(ttl=ROUTE_TTL["institutional_action"], key="institutional_action")
def api_institutional_action(portfolio: str | None = None):
    payload = _build_institutional_payload(portfolio)
    return payload["recommended_action"]


@app.post("/api/institutional/audit/decisions")
def api_record_institutional_decision(portfolio: str | None = None):
    payload = _build_institutional_payload(portfolio)
    record = get_audit_store().record_decision(payload, source="api")
    invalidate("institutional_audit_log")
    invalidate("institutional_reviews_due")
    invalidate("institutional_reviews_summary")
    invalidate("institutional_review_scores")
    invalidate("institutional_review_outcomes")
    return {
        "record": {k: v for k, v in record.items() if k != "payload"},
        "payload": payload,
    }


@app.get("/api/institutional/audit/decisions")
def api_list_institutional_decisions(limit: int = 20):
    return {"decisions": get_audit_store().list_decisions(limit=limit)}


@app.get("/api/institutional/audit/verify")
def api_verify_institutional_audit(limit: int = Query(100, ge=1, le=500)):
    return get_audit_store().verify_recent_decisions(limit=limit)


@app.get("/api/institutional/audit/decisions/{ticket_id}")
def api_get_institutional_decision(ticket_id: str):
    record = get_audit_store().get_decision(ticket_id)
    if record is None:
        return JSONResponse(content={"error": "decision ticket not found"}, status_code=404)
    return record


@app.get("/api/institutional/audit/decisions/{ticket_id}/verify")
def api_verify_institutional_decision(ticket_id: str):
    verification = get_audit_store().verify_decision(ticket_id)
    if verification is None:
        return JSONResponse(content={"error": "decision ticket not found"}, status_code=404)
    return verification


@app.get("/api/institutional/reviews/due")
@cached(ttl=ROUTE_TTL["institutional_reviews_due"], key="institutional_reviews_due")
def api_institutional_due_reviews():
    store = get_audit_store()
    rows = store.list_decisions(limit=100)
    review_scores = store.list_review_scores(limit=500)
    return {"reviews": list_due_reviews(rows, now=time.time(), review_scores=review_scores)}


@app.get("/api/institutional/reviews/summary")
@cached(ttl=ROUTE_TTL["institutional_reviews_summary"], key="institutional_reviews_summary")
def api_institutional_review_summary():
    store = get_audit_store()
    rows = store.list_decisions(limit=100)
    review_scores = store.list_review_scores(limit=500)
    return {"summary": build_review_summary(rows, review_scores, now=time.time())}


@app.get("/api/institutional/reviews/queue")
def api_institutional_review_queue(priority: str | None = None, limit: int = Query(50, ge=1, le=100)):
    store = get_audit_store()
    rows = store.list_decisions(limit=100)
    review_scores = store.list_review_scores(limit=500)
    try:
        queue = build_review_queue(rows, review_scores, now=time.time(), priority=priority, limit=limit)
    except ValueError as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=400)
    return {
        "queue": queue,
        "returned_count": len(queue),
        "filters": {
            "priority": priority,
            "limit": limit,
        },
    }


@app.get("/api/institutional/reviews/{ticket_id}/score")
def api_score_institutional_review(ticket_id: str, window: str = "T+1"):
    record = get_audit_store().get_decision(ticket_id)
    if record is None:
        return JSONResponse(content={"error": "decision ticket not found"}, status_code=404)
    return score_review(record, review_window=window)


@app.post("/api/institutional/reviews/{ticket_id}/score")
def api_record_institutional_review_score(ticket_id: str, window: str = "T+1"):
    store = get_audit_store()
    record = store.get_decision(ticket_id)
    if record is None:
        return JSONResponse(content={"error": "decision ticket not found"}, status_code=404)
    review_score = score_review(record, review_window=window)
    stored = store.record_review_score(review_score)
    invalidate("institutional_review_outcomes")
    invalidate("institutional_review_scores")
    invalidate("institutional_reviews_due")
    invalidate("institutional_reviews_summary")
    return {"recorded": True, "score": stored}


@app.get("/api/institutional/reviews/scores")
def api_list_institutional_review_scores(ticket_id: str | None = None, limit: int = 50):
    return {"scores": get_audit_store().list_review_scores(ticket_id=ticket_id, limit=limit)}


@app.get("/api/institutional/reviews/scores/due")
@cached(ttl=ROUTE_TTL["institutional_review_scores"], key="institutional_review_scores")
def api_score_due_institutional_reviews():
    store = get_audit_store()
    review_scores = store.list_review_scores(limit=500)
    due = list_due_reviews(store.list_decisions(limit=100), now=time.time(), review_scores=review_scores)
    scored = []
    for item in due:
        record = store.get_decision(item["ticket_id"])
        if record is not None:
            scored.append(score_review(record, review_window=item["window"]))
    return {"scores": scored}


@app.post("/api/institutional/reviews/scores/due")
def api_record_due_institutional_review_scores():
    store = get_audit_store()
    review_scores = store.list_review_scores(limit=500)
    due = list_due_reviews(store.list_decisions(limit=100), now=time.time(), review_scores=review_scores)
    scored = []
    for item in due:
        record = store.get_decision(item["ticket_id"])
        if record is not None:
            scored.append(store.record_review_score(score_review(record, review_window=item["window"])))
    invalidate("institutional_review_scores")
    invalidate("institutional_review_outcomes")
    invalidate("institutional_reviews_due")
    invalidate("institutional_reviews_summary")
    return {"recorded_count": len(scored), "scores": scored}


@app.get("/api/institutional/morning_brief")
async def api_institutional_morning_brief():
    try:
        portfolio = build_portfolio_snapshot(load_portfolio_positions("data/institutional_portfolio.json"))
        
        # We need to compute multiple things concurrently for speed, but for simplicity we can do it sequentially or use asyncio if we wrap them.
        # compute_decision_matrix uses DATA_CACHE extensively.
        decision_matrix = compute_decision_matrix(portfolio=portfolio)
        
        # factor risk
        factor_risk = build_factor_risk_snapshot(portfolio)
        
        # scenarios
        scenarios = run_portfolio_scenarios(portfolio)
        
        # macro context
        from core.market_data import DATA_CACHE
        def get_last_val(key, default=0.0):
            d = DATA_CACHE.get(key, {}).get("data")
            if d is None: return default
            vals = d.get("data", d) if isinstance(d, dict) else d
            if hasattr(vals, "iloc"): return float(vals.iloc[-1]) if len(vals) > 0 else default
            elif isinstance(vals, (list, tuple, str)): return float(vals[-1]) if len(vals) > 0 else default
            return default
            
        macro_data = {
            "vix": get_last_val("vix", 20.0),
            "tnx": get_last_val("tnx", 4.0)
        }
        
        brief_result = generate_morning_brief(decision_matrix, scenarios, factor_risk, macro_data)
        
        return {"status": "ok", "timestamp": int(time.time()), "data": brief_result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/gateway/status")
def api_gateway_status():
    try:
        import time
        status_file = os.path.join(os.path.dirname(__file__), "qmt_heartbeat.json")
        if not os.path.exists(status_file):
            return {"status": "OFFLINE", "reason": "Heartbeat file not found"}
        
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Check heartbeat timeout (e.g. 25 seconds)
        heartbeat_time = data.get("timestamp", 0)
        if time.time() - heartbeat_time > 25.0:
            return {"status": "OFFLINE", "reason": "Heartbeat timeout"}
            
        return {
            "status": "ONLINE",
            "has_xtquant": data.get("has_xtquant", False),
            "dry_run": data.get("dry_run", True),
            "account_id": data.get("account_id", ""),
            "data_dir": data.get("data_dir", ""),
            "timestamp": heartbeat_time
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


class SignOffOrder(BaseModel):
    symbol: str
    side: str
    quantity: int
    price: float
    execution_algo: str

class SignOffOrdersRequest(BaseModel):
    orders: list[SignOffOrder]

@app.post("/api/institutional/sign_off_orders")
def api_sign_off_orders(req: SignOffOrdersRequest):
    try:
        from core.db_layer import record_trade
        import uuid
        import datetime
        
        today_str = datetime.date.today().strftime("%Y%m%d")
        signed_orders = []
        
        for ord_req in req.orders:
            order_uuid = str(uuid.uuid4())[:8].upper()
            unique_id = f"{today_str}_{order_uuid}"
            
            # Record in SQLite as PENDING
            record_trade(
                order_id=unique_id,
                symbol=ord_req.symbol,
                side=ord_req.side.upper(),
                quantity=int(ord_req.quantity),
                price=float(ord_req.price),
                status="PENDING",
                execution_algo=ord_req.execution_algo,
                benchmark_price=float(ord_req.price)
            )
            signed_orders.append({
                "order_id": unique_id,
                "symbol": ord_req.symbol,
                "execution_algo": ord_req.execution_algo
            })
            
        return {"status": "success", "signed_orders": signed_orders}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


class ExecuteTradeRequest(BaseModel):
    ticker: str
    action: str
    qty: float

@app.post("/api/execute")
def api_execute_trade(req: ExecuteTradeRequest, portfolio: str | None = None):
    try:
        from core.db_layer import record_trade
        import uuid
        import time
        order_id = str(uuid.uuid4())[:8].upper()
        # Mock price for now, or fetch from market data if needed
        price = 100.0 
        p_id = portfolio or "institutional_portfolio"
        record_trade(order_id, req.ticker, req.action.upper(), int(req.qty), price, "EXECUTED", portfolio_id=p_id)
        return {"status": "success", "order_id": order_id, "message": f"{req.action} {req.qty} {req.ticker} executed"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/institutional/global_risk_net")
def api_institutional_global_risk_net():
    try:
        from core.portfolio_book import get_available_portfolios, load_portfolio_positions, build_portfolio_snapshot
        from core.scenario_engine import run_global_risk_net
        books = get_available_portfolios()
        snapshots = []
        for b in books:
            name = b["name"]
            positions = load_portfolio_positions(name)
            snap = build_portfolio_snapshot(positions)
            snap["portfolio_name"] = name
            snap["display_name"] = b.get("display_name", name)
            snapshots.append(snap)
            
        joint_stress = run_global_risk_net(snapshots)
        
        # Check global compliance sentinel breach
        global_status = "NORMAL"
        worst = joint_stress.get("worst_scenario")
        if worst and worst.get("portfolio_loss_pct", 0.0) < -12.0:
            global_status = "CROSS_PORTFOLIO_WARNING"
            
        joint_stress["global_status"] = global_status
        return joint_stress
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/audit_trail")
def api_audit_trail(limit: int = 50, portfolio: str | None = None):
    try:
        from core.db_layer import get_recent_trades
        trades = get_recent_trades(limit=limit, portfolio_id=portfolio)
        return {"status": "success", "trades": trades}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("data_engine:app", host="127.0.0.1", port=8888, reload=True)
