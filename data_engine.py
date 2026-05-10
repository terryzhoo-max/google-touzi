import time
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import refactored core modules
from core.market_data import background_data_fetcher, fetch_yfinance_data
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

from core.cache_store import cached_async, ROUTE_TTL, get_cache_stats
from core.config import settings

app = FastAPI(title="AlphaCore Quant Data Engine")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_data_fetcher())

from core.market_data import shutdown_event

@app.on_event("shutdown")
async def shutdown_event_handler():
    print("Shutting down background tasks...")
    shutdown_event.set()


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# --- API Routes ---

@app.get("/api/health")
async def api_health():
    """System health — data source status + cache metrics."""
    from core.data_providers import get_provider_stats
    from core.alert_state import get_active_alerts
    ps = get_provider_stats()
    degraded = [k for k, v in ps.items() if v.get("error_rate", 0) > 0.3]
    return {
        "status": "degraded" if degraded else "healthy",
        "degraded_sources": degraded,
        "sources": ps,
        "cache": get_cache_stats(),
        "rate_limit": {
            "window_sec": 60,
            "max_requests_per_minute": settings.MAX_REQUESTS_PER_MINUTE,
            "tracked_clients": len(RATE_LIMIT_DB),
        },
        "active_alerts": len(get_active_alerts()),
        "routes": list(ROUTE_TTL.keys()),
    }

@app.get("/api/macro/erp")
@cached_async(ttl=ROUTE_TTL["erp"], key="erp")
async def get_erp_data():
    return fetch_yfinance_data("^TNX", "tnx")

@app.get("/api/macro/spread")
@cached_async(ttl=ROUTE_TTL["spread"], key="spread")
async def get_spread_data():
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
@cached_async(ttl=ROUTE_TTL["yield_curve"], key="yield_curve")
async def api_yield_curve():
    return get_yield_curve(days=120)

@app.get("/api/macro/allocation")
@cached_async(ttl=ROUTE_TTL["allocation"], key="allocation")
async def get_asset_allocation():
    return calculate_asset_allocation()

@app.get("/api/macro/correlation")
@cached_async(ttl=ROUTE_TTL["correlation"], key="correlation")
async def get_correlation_matrix():
    return calculate_correlation_matrix()

@app.get("/api/macro/montecarlo")
@cached_async(ttl=ROUTE_TTL["montecarlo"], key="montecarlo")
async def get_montecarlo_sim():
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
@cached_async(ttl=ROUTE_TTL["sector_rotation"], key="sector_rotation")
async def api_sector_rotation():
    return get_sector_rotation(days_back=90)

@app.get("/api/macro/theme_rotation")
@cached_async(ttl=ROUTE_TTL["theme_rotation"], key="theme_rotation")
async def api_theme_rotation():
    return get_theme_rotation()

@app.get("/api/macro/domestic_etf")
@cached_async(ttl=ROUTE_TTL["domestic_etf"], key="domestic_etf")
async def api_domestic_etf():
    return get_domestic_etf_rotation()

@app.get("/api/macro/global_etf")
@cached_async(ttl=ROUTE_TTL["global_etf"], key="global_etf")
async def api_global_etf():
    return get_global_etf_rotation()

@app.get("/api/macro/fed_prob")
@cached_async(ttl=ROUTE_TTL["fed_prob"], key="fed_prob")
async def api_fed_prob():
    return get_fed_probability()

@app.get("/api/macro/global_assets")
@cached_async(ttl=ROUTE_TTL["global_assets"], key="global_assets")
async def api_global_assets():
    return get_global_assets()

@app.get("/api/macro/valuation")
@cached_async(ttl=ROUTE_TTL["valuation"], key="valuation")
async def api_valuation():
    return get_valuation()

@app.get("/api/macro/china_macro")
@cached_async(ttl=ROUTE_TTL["china_macro"], key="china_macro")
async def api_china_macro():
    return get_china_macro(months=24)

@app.get("/api/macro/market_breadth")
@cached_async(ttl=ROUTE_TTL["market_breadth"], key="market_breadth")
async def api_market_breadth():
    return get_market_breadth(days=60)

@app.get("/api/macro/signals")
@cached_async(ttl=ROUTE_TTL["signals"], key="signals")
async def api_signals():
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

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("data_engine:app", host="127.0.0.1", port=8888, reload=True)
