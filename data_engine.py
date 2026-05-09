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

from core.cache_store import cached, cached_async, ROUTE_TTL, get_cache_stats, invalidate

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Phase 12: Institutional Security (Rate Limiting) ---
from collections import defaultdict
from core.config import settings
RATE_LIMIT_DB = defaultdict(list)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    now = time.time()
    RATE_LIMIT_DB[client_ip] = [t for t in RATE_LIMIT_DB[client_ip] if now - t < 60]
    
    if len(RATE_LIMIT_DB[client_ip]) >= settings.MAX_REQUESTS_PER_MINUTE:
        return JSONResponse(status_code=429, content={"detail": "Too Many Requests. 机构级 API 风控防御机制已触发，已拦截异常高频访问。"})
        
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
        "active_alerts": len(get_active_alerts()),
        "routes": list(ROUTE_TTL.keys()),
    }

@cached_async(ttl=ROUTE_TTL["erp"], key="erp")
@app.get("/api/macro/erp")
async def get_erp_data():
    return fetch_yfinance_data("^TNX", "tnx")

@cached_async(ttl=ROUTE_TTL["spread"], key="spread")
@app.get("/api/macro/spread")
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

@cached_async(ttl=ROUTE_TTL["decision"], key="decision")
@app.get("/api/macro/decision")
async def api_decision():
    return await _build_decision_payload()

@cached_async(ttl=ROUTE_TTL["yield_curve"], key="yield_curve")
@app.get("/api/macro/yield_curve")
async def api_yield_curve():
    return get_yield_curve(days=120)

@cached_async(ttl=ROUTE_TTL["allocation"], key="allocation")
@app.get("/api/macro/allocation")
async def get_asset_allocation():
    return calculate_asset_allocation()

@cached_async(ttl=ROUTE_TTL["correlation"], key="correlation")
@app.get("/api/macro/correlation")
async def get_correlation_matrix():
    return calculate_correlation_matrix()

@cached_async(ttl=ROUTE_TTL["montecarlo"], key="montecarlo")
@app.get("/api/macro/montecarlo")
async def get_montecarlo_sim():
    return run_montecarlo_sim()

@cached_async(ttl=ROUTE_TTL["efficient_frontier"], key="efficient_frontier")
@app.get("/api/macro/efficient_frontier")
async def api_efficient_frontier():
    return await asyncio.to_thread(run_efficient_frontier)

@cached_async(ttl=ROUTE_TTL["scenario"], key="scenario")
@app.get("/api/macro/scenario")
async def api_scenario():
    return await asyncio.to_thread(run_scenario_analysis)

@cached_async(ttl=3600, key="sector_rotation")
@app.get("/api/macro/sector_rotation")
async def api_sector_rotation():
    return get_sector_rotation(days_back=90)

@cached_async(ttl=3600, key="theme_rotation")
@app.get("/api/macro/theme_rotation")
async def api_theme_rotation():
    return get_theme_rotation()

@cached_async(ttl=3600, key="domestic_etf")
@app.get("/api/macro/domestic_etf")
async def api_domestic_etf():
    return get_domestic_etf_rotation()

@cached_async(ttl=3600, key="global_etf")
@app.get("/api/macro/global_etf")
async def api_global_etf():
    return get_global_etf_rotation()

@cached_async(ttl=3600, key="fed_prob")
@app.get("/api/macro/fed_prob")
async def api_fed_prob():
    return get_fed_probability()

@cached_async(ttl=3600, key="global_assets")
@app.get("/api/macro/global_assets")
async def api_global_assets():
    return get_global_assets()

@cached_async(ttl=43200, key="valuation")
@app.get("/api/macro/valuation")
async def api_valuation():
    return get_valuation()

@cached_async(ttl=86400, key="china_macro")
@app.get("/api/macro/china_macro")
async def api_china_macro():
    return get_china_macro(months=24)

@cached_async(ttl=3600, key="market_breadth")
@app.get("/api/macro/market_breadth")
async def api_market_breadth():
    return get_market_breadth(days=60)

@cached_async(ttl=ROUTE_TTL["signals"], key="signals")
@app.get("/api/macro/signals")
async def api_signals():
    return get_multi_timeframe_signals()

@cached_async(ttl=ROUTE_TTL["ai_insight"], key="ai_insight")
@app.get("/api/macro/ai_insight")
async def get_ai_insight():
    # Phase 22: Async non-blocking thread offloading to prevent event loop lock
    return await asyncio.to_thread(generate_llm_insight)


from core.backtest import run_backtest

@cached_async(ttl=ROUTE_TTL["backtest"], key="backtest")
@app.get("/api/macro/backtest")
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
