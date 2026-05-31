import asyncio

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from core.asset_rotation import get_domestic_etf_rotation, get_global_etf_rotation, get_theme_rotation
from core.backtest import run_backtest
from core.cache_store import ROUTE_TTL, cached, cached_async
from core.china_macro import get_china_macro
from core.decision_signal import compute_decision
from core.dividend_yield import get_dividend_leaders
from core.fed_prob import get_fed_probability
from core.global_assets import get_global_assets
from core.llm_agent import generate_llm_insight
from core.margin_monitor import get_margin_data
from core.market_breadth import get_market_breadth
from core.market_data import fetch_yfinance_data
from core.portfolio_manager import get_portfolio_summary
from core.portfolio_opt import run_efficient_frontier
from core.quant_engine import calculate_asset_allocation, calculate_correlation_matrix, run_montecarlo_sim
from core.scenario import run_scenario_analysis
from core.sector_rotation import get_sector_rotation
from core.signals import get_multi_timeframe_signals
from core.surprise_index import get_surprise_index
from core.valuation import get_valuation
from core.yield_curve import get_yield_curve


async def build_decision_payload() -> dict:
    vix_data, tnx_data, yc_data, corr_data = await asyncio.gather(
        asyncio.to_thread(fetch_yfinance_data, "^VIX", "vix"),
        asyncio.to_thread(fetch_yfinance_data, "^TNX", "tnx"),
        asyncio.to_thread(get_yield_curve, 60),
        asyncio.to_thread(calculate_correlation_matrix),
    )

    try:
        vix = float(vix_data["data"][-1]) if vix_data.get("data") else 20.0
    except Exception:
        vix = 20.0
    try:
        tnx = float(tnx_data["data"][-1]) if tnx_data.get("data") else 4.0
    except Exception:
        tnx = 4.0

    spy_tlt_corr = 0.0
    if corr_data.get("matrix"):
        for item in corr_data["matrix"]:
            if (item[0] == 0 and item[1] == 1) or (item[0] == 1 and item[1] == 0):
                spy_tlt_corr = float(item[2])
                break

    regime, alloc = "NEUTRAL CHOP", {"spy": 60, "tlt": 30, "gld": 10, "cash": 0}
    try:
        bt = await asyncio.to_thread(run_backtest)
        state = bt.get("current_state", {})
        regime = state.get("regime", regime)
        alloc = {
            "spy": state.get("w_spy", 60),
            "tlt": state.get("w_tlt", 30),
            "gld": state.get("w_gld", 10),
            "cash": state.get("w_cash", 0),
        }
    except Exception:
        pass

    china_data = {}
    pe_pct = 50.0
    try:
        china_data, val_data = await asyncio.gather(
            asyncio.to_thread(get_china_macro, 12),
            asyncio.to_thread(get_valuation),
        )
        for idx in val_data.get("indices", []):
            if "300" in idx.get("name", ""):
                pe_pct = float(idx.get("pe_pct", 50))
                break
    except Exception:
        pass

    result = compute_decision(
        vix=vix,
        tnx=tnx,
        tnx_data=tnx_data,
        yc_data=yc_data,
        spy_tlt_corr=spy_tlt_corr,
        regime=regime,
        china=china_data,
        pe_pct=pe_pct,
    )
    result["regime_alloc"] = alloc
    return result


def register_macro_routes(app: FastAPI) -> None:
    router = APIRouter()

    @router.get("/api/macro/erp")
    @cached(ttl=ROUTE_TTL["erp"], key="erp")
    def get_erp_data():
        return fetch_yfinance_data("^TNX", "tnx")

    @router.get("/api/macro/spread")
    @cached(ttl=ROUTE_TTL["spread"], key="spread")
    def get_spread_data():
        return fetch_yfinance_data("^VIX", "vix")

    @router.get("/api/macro/decision")
    @cached_async(ttl=ROUTE_TTL["decision"], key="decision")
    async def api_decision():
        return await build_decision_payload()

    @router.get("/api/macro/yield_curve")
    @cached(ttl=ROUTE_TTL["yield_curve"], key="yield_curve")
    def api_yield_curve():
        return get_yield_curve(days=120)

    @router.get("/api/macro/allocation")
    @cached(ttl=ROUTE_TTL["allocation"], key="allocation")
    def get_asset_allocation():
        return calculate_asset_allocation()

    @router.get("/api/macro/correlation")
    @cached(ttl=ROUTE_TTL["correlation"], key="correlation")
    def get_correlation_matrix():
        return calculate_correlation_matrix()

    @router.get("/api/macro/montecarlo")
    @cached(ttl=ROUTE_TTL["montecarlo"], key="montecarlo")
    def get_montecarlo_sim():
        return run_montecarlo_sim()

    @router.get("/api/macro/efficient_frontier")
    @cached_async(ttl=ROUTE_TTL["efficient_frontier"], key="efficient_frontier")
    async def api_efficient_frontier():
        return await asyncio.to_thread(run_efficient_frontier)

    @router.get("/api/macro/scenario")
    @cached_async(ttl=ROUTE_TTL["scenario"], key="scenario")
    async def api_scenario():
        return await asyncio.to_thread(run_scenario_analysis)

    @router.get("/api/macro/sector_rotation")
    @cached(ttl=ROUTE_TTL["sector_rotation"], key="sector_rotation")
    def api_sector_rotation():
        return get_sector_rotation(days_back=90)

    @router.get("/api/macro/theme_rotation")
    @cached(ttl=ROUTE_TTL["theme_rotation"], key="theme_rotation")
    def api_theme_rotation():
        return get_theme_rotation()

    @router.get("/api/macro/domestic_etf")
    @cached(ttl=ROUTE_TTL["domestic_etf"], key="domestic_etf")
    def api_domestic_etf():
        return get_domestic_etf_rotation()

    @router.get("/api/macro/global_etf")
    @cached(ttl=ROUTE_TTL["global_etf"], key="global_etf")
    def api_global_etf():
        return get_global_etf_rotation()

    @router.get("/api/macro/fed_prob")
    @cached(ttl=ROUTE_TTL["fed_prob"], key="fed_prob")
    def api_fed_prob():
        return get_fed_probability()

    @router.get("/api/macro/global_assets")
    @cached(ttl=ROUTE_TTL["global_assets"], key="global_assets_v4")
    def api_global_assets():
        return get_global_assets()

    @router.get("/api/macro/valuation")
    @cached(ttl=ROUTE_TTL["valuation"], key="valuation")
    def api_valuation():
        return get_valuation()

    @router.get("/api/macro/surprise_index")
    @cached(ttl=43200, key="surprise_index")
    def api_surprise_index():
        return get_surprise_index(months=36)

    @router.get("/api/portfolio/summary")
    @cached(ttl=600, key="portfolio_summary")
    def api_portfolio():
        return get_portfolio_summary()

    @router.get("/api/macro/margin")
    @cached(ttl=3600, key="margin_v2")
    def api_margin():
        return get_margin_data(days=60)

    @router.get("/api/macro/dividend")
    @cached(ttl=43200, key="dividend_v7")
    def api_dividend():
        return get_dividend_leaders(limit=10)

    @router.get("/api/macro/china_macro")
    @cached(ttl=ROUTE_TTL["china_macro"], key="china_macro")
    def api_china_macro():
        return get_china_macro(months=24)

    @router.get("/api/macro/market_breadth")
    @cached(ttl=ROUTE_TTL["market_breadth"], key="market_breadth")
    def api_market_breadth():
        return get_market_breadth(days=60)

    @router.get("/api/macro/signals")
    @cached(ttl=ROUTE_TTL["signals"], key="signals")
    def api_signals():
        return get_multi_timeframe_signals()

    @router.get("/api/macro/ai_insight")
    @cached_async(ttl=ROUTE_TTL["ai_insight"], key="ai_insight")
    async def get_ai_insight():
        return await asyncio.to_thread(generate_llm_insight)

    @router.get("/api/macro/backtest")
    @cached_async(ttl=ROUTE_TTL["backtest"], key="backtest")
    async def api_backtest():
        try:
            data = await asyncio.to_thread(run_backtest)
            if "error" in data:
                return JSONResponse(content={"error": data["error"]}, status_code=500)
            return data
        except Exception as exc:
            print(f"Backtest error: {exc}")
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    app.include_router(router)
