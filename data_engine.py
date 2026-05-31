import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.factory import create_app, mount_static_assets
from app.routes.alerts import register_alert_routes
from app.routes.audit import register_audit_routes
from app.routes.execution import register_execution_routes
from app.routes.health import register_health_routes
from app.routes.institutional import register_institutional_core_routes
from app.routes.macro import build_decision_payload as _macro_build_decision_payload
from app.routes.macro import register_macro_routes
from app.schemas import AllocationModelSimulateRequest
from app.services import institutional_decision_service as institutional_service
from core.asset_rotation import get_domestic_etf_rotation, get_global_etf_rotation
from core.allocation_model import build_allocation_recommendation
from core.config import settings
from core.market_data import background_data_fetcher, shutdown_event
from core.valuation import get_valuation





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





app = create_app(lifespan=lifespan, settings=settings)
RATE_LIMIT_DB = app.state.rate_limit_db
register_alert_routes(app)
register_health_routes(app, settings=settings, rate_limit_db=RATE_LIMIT_DB)
register_macro_routes(app)


def run_historical_replication_analysis_wrapper(portfolio_snapshot: dict, benchmark, portfolio_name: str | None) -> dict:
    return institutional_service.run_historical_replication_analysis_wrapper(portfolio_snapshot, benchmark, portfolio_name)


def _build_institutional_payload(portfolio_name: str | None = None) -> dict:
    return institutional_service.build_institutional_payload(
        portfolio_name,
        allocation_builder=build_allocation_recommendation,
        market_context_builder=_build_institutional_market_context,
    )


def _build_institutional_portfolio(portfolio_name: str | None = None) -> dict:
    return institutional_service.build_institutional_portfolio(portfolio_name)


def _build_institutional_data_quality(portfolio_name: str | None = None) -> dict:
    return institutional_service.build_institutional_data_quality(portfolio_name)


def _build_institutional_market_context() -> dict:
    return institutional_service.build_institutional_market_context(
        valuation_fn=get_valuation,
        domestic_rotation_fn=get_domestic_etf_rotation,
        global_rotation_fn=get_global_etf_rotation,
    )


def _build_institutional_allocation_model(portfolio: dict | None = None, data_quality: dict | None = None) -> dict:
    return institutional_service.build_institutional_allocation_model(
        portfolio=portfolio,
        data_quality=data_quality,
        allocation_builder=build_allocation_recommendation,
        market_context_builder=_build_institutional_market_context,
    )


def _build_allocation_model_degraded_packet(portfolio: dict, data_quality: dict, exc: Exception) -> dict:
    return institutional_service.build_allocation_model_degraded_packet(portfolio, data_quality, exc)


def _build_simulated_data_quality(request: AllocationModelSimulateRequest) -> dict:
    return institutional_service.build_simulated_data_quality(request)


def _build_institutional_what_if(portfolio: dict, adjustments: dict[str, float], portfolio_name: str | None = None) -> dict:
    return institutional_service.build_institutional_what_if(portfolio, adjustments, portfolio_name)


async def _build_decision_payload():
    return await _macro_build_decision_payload()


register_institutional_core_routes(
    app,
    build_portfolio=_build_institutional_portfolio,
    build_data_quality=_build_institutional_data_quality,
    build_payload=_build_institutional_payload,
    build_allocation_model=_build_institutional_allocation_model,
    build_simulated_data_quality=_build_simulated_data_quality,
    build_what_if=_build_institutional_what_if,
    allocation_builder=build_allocation_recommendation,
    settings=settings,
    base_dir=os.path.dirname(__file__),
)
register_audit_routes(app, build_payload=_build_institutional_payload)
register_execution_routes(app, settings=settings, base_dir=os.path.dirname(__file__))



# --- Static Assets ---


mount_static_assets(app)


if __name__ == "__main__":

    import uvicorn

    uvicorn.run("data_engine:app", host="127.0.0.1", port=8888, reload=True)
