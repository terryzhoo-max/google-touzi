import time
import asyncio
import os
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, Query, Request
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

# Import refactored core modules
from core.market_data import background_data_fetcher, fetch_yfinance_data, shutdown_event
from core.quant_engine import calculate_asset_allocation, calculate_correlation_matrix, run_montecarlo_sim
from core.llm_agent import generate_llm_insight
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
    vix_data = fetch_yfinance_data("^VIX", "vix")
    tnx_data = fetch_yfinance_data("^TNX", "tnx")
    yc_data  = get_yield_curve(days=60)
    corr_data = await asyncio.to_thread(calculate_correlation_matrix)

    try:    vix = float(vix_data["data"][-1]) if vix_data.get("data") else 20.0
    except Exception: vix = 20.0
    try:    tnx = float(tnx_data["data"][-1]) if tnx_data.get("data") else 4.0
    except Exception: tnx = 4.0

    spy_tlt_corr = 0.0
    if corr_data.get("matrix"):
        for item in corr_data["matrix"]:
            if (item[0] == 0 and item[1] == 1) or (item[0] == 1 and item[1] == 0):
                spy_tlt_corr = float(item[2]); break

    regime, alloc = "中性震荡", {"spy":60,"tlt":30,"gld":10,"cash":0}
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
        china_data = get_china_macro(months=12)
        val_data = get_valuation()
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
@cached(ttl=43200, key="dividend_v6")
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


def _build_institutional_payload() -> dict:
    policy = get_default_decision_policy()
    portfolio = _build_institutional_portfolio()
    data_quality = _build_institutional_data_quality()
    risk = calculate_portfolio_risk(portfolio)
    scenarios = run_portfolio_scenarios(portfolio)
    factor_risk = build_factor_risk_snapshot(portfolio)
    benchmark = build_default_benchmark()
    benchmark_payload = benchmark_to_dict(benchmark)
    active_risk = build_active_risk_snapshot(portfolio, benchmark)
    attribution = build_attribution_snapshot(portfolio, benchmark, period="T+1")
    ticket = build_decision_ticket(data_quality, risk, scenarios, portfolio=portfolio, policy=policy)
    what_if = _build_institutional_what_if(portfolio, build_default_risk_reduction_adjustments(portfolio))
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
        "audit": {
            "recorded": False,
            "record_endpoint": "/api/institutional/audit/decisions",
            "review_schedule": ticket["review_schedule"],
        },
    }


def _build_institutional_portfolio() -> dict:
    return build_portfolio_snapshot(load_portfolio_positions(settings.PORTFOLIO_BOOK_PATH))


def _build_institutional_data_quality() -> dict:
    has_portfolio_file = bool(settings.PORTFOLIO_BOOK_PATH) and os.path.exists(settings.PORTFOLIO_BOOK_PATH)
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


def _build_institutional_what_if(portfolio: dict, adjustments: dict[str, float]) -> dict:
    what_if = run_what_if(portfolio, adjustments)
    data_quality = _build_institutional_data_quality()
    current_risk = calculate_portfolio_risk(portfolio)
    what_if["compliance"] = evaluate_pre_trade_compliance(
        portfolio,
        what_if["after"]["portfolio"],
        data_quality=data_quality,
        current_risk=current_risk,
    )
    return what_if


@app.get("/api/institutional/portfolio")
@cached(ttl=ROUTE_TTL["institutional_portfolio"], key="institutional_portfolio")
def api_institutional_portfolio():
    return _build_institutional_portfolio()


@app.get("/api/institutional/data_quality")
@cached(ttl=ROUTE_TTL["institutional_data_quality"], key="institutional_data_quality")
def api_institutional_data_quality():
    return _build_institutional_data_quality()


@app.get("/api/institutional/risk")
@cached(ttl=ROUTE_TTL["institutional_risk"], key="institutional_risk")
def api_institutional_risk():
    portfolio = _build_institutional_portfolio()
    risk = calculate_portfolio_risk(portfolio)
    return risk


@app.get("/api/institutional/scenarios")
@cached(ttl=ROUTE_TTL["institutional_scenarios"], key="institutional_scenarios")
def api_institutional_scenarios():
    portfolio = _build_institutional_portfolio()
    scenarios = run_portfolio_scenarios(portfolio)
    return scenarios


@app.get("/api/institutional/factors")
@cached(ttl=ROUTE_TTL["institutional_factors"], key="institutional_factors")
def api_institutional_factors():
    return build_factor_risk_snapshot(_build_institutional_portfolio())


@app.get("/api/institutional/benchmark")
@cached(ttl=ROUTE_TTL["institutional_benchmark"], key="institutional_benchmark")
def api_institutional_benchmark():
    return benchmark_to_dict(build_default_benchmark())


@app.get("/api/institutional/active_risk")
@cached(ttl=ROUTE_TTL["institutional_active_risk"], key="institutional_active_risk")
def api_institutional_active_risk():
    portfolio = _build_institutional_portfolio()
    return build_active_risk_snapshot(portfolio, build_default_benchmark())


@app.get("/api/institutional/attribution")
def api_institutional_attribution(period: str = "T+1"):
    portfolio = _build_institutional_portfolio()
    return build_attribution_snapshot(portfolio, build_default_benchmark(), period=period)


@app.get("/api/institutional/compliance")
@cached(ttl=ROUTE_TTL["institutional_compliance"], key="institutional_compliance")
def api_institutional_compliance():
    portfolio = _build_institutional_portfolio()
    what_if = _build_institutional_what_if(portfolio, build_default_risk_reduction_adjustments(portfolio))
    return what_if["compliance"]


@app.post("/api/institutional/compliance/check")
def api_institutional_compliance_check(request: WhatIfRequest):
    try:
        portfolio = _build_institutional_portfolio()
        what_if = _build_institutional_what_if(portfolio, request.adjustments)
        return what_if["compliance"]
    except ValueError as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=400)


@app.get("/api/institutional/decision")
@cached(ttl=ROUTE_TTL["institutional_decision"], key="institutional_decision")
def api_institutional_decision():
    return _build_institutional_payload()


@app.get("/api/institutional/policy")
@cached(ttl=ROUTE_TTL["institutional_policy"], key="institutional_policy")
def api_institutional_policy():
    return get_default_decision_policy()


@app.get("/api/institutional/allocation_model")
@cached(ttl=ROUTE_TTL["institutional_allocation_model"], key="institutional_allocation_model")
def api_institutional_allocation_model():
    return _build_institutional_allocation_model()


@app.get("/api/institutional/allocation_model/policy")
@cached(ttl=ROUTE_TTL["institutional_allocation_model_policy"], key="institutional_allocation_model_policy")
def api_institutional_allocation_model_policy():
    return allocation_policy_to_dict(get_default_allocation_policy())


@app.post("/api/institutional/allocation_model/simulate")
def api_institutional_allocation_model_simulate(request: AllocationModelSimulateRequest):
    portfolio = _build_institutional_portfolio()
    return build_allocation_recommendation(
        portfolio,
        data_quality=_build_simulated_data_quality(request),
        market_context=request.market_context,
    )


@app.post("/api/institutional/allocation_model/audit")
def api_record_institutional_allocation_model():
    payload = _build_institutional_payload()
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
def api_institutional_what_if_default():
    portfolio = _build_institutional_portfolio()
    return _build_institutional_what_if(portfolio, build_default_risk_reduction_adjustments(portfolio))


@app.post("/api/institutional/what_if")
def api_institutional_what_if(request: WhatIfRequest):
    try:
        portfolio = _build_institutional_portfolio()
        return _build_institutional_what_if(portfolio, request.adjustments)
    except ValueError as exc:
        return JSONResponse(content={"error": str(exc)}, status_code=400)


@app.get("/api/institutional/action")
@cached(ttl=ROUTE_TTL["institutional_action"], key="institutional_action")
def api_institutional_action():
    payload = _build_institutional_payload()
    return payload["recommended_action"]


@app.post("/api/institutional/audit/decisions")
def api_record_institutional_decision():
    payload = _build_institutional_payload()
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


app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("data_engine:app", host="127.0.0.1", port=8888, reload=True)
