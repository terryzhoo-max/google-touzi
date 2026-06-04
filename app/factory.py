import asyncio
import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


DEFAULT_ROUTE_TIMEOUTS = {
    "/api/macro/backtest": 60,
    "/api/macro/correlation": 30,
    "/api/macro/montecarlo": 30,
    "/api/macro/efficient_frontier": 30,
    "/api/macro/decision": 45,
    "/api/institutional/decision": 45,
    "/api/macro/global_assets": 30,
    "/api/macro/valuation": 30,
}

POLLING_RATE_LIMIT_PATHS = {
    "/api/audit_trail",
}


def _rate_limit_bucket(client_ip: str, path: str) -> tuple[str, str]:
    if path in POLLING_RATE_LIMIT_PATHS:
        return (client_ip, path)
    return (client_ip, "core")


def _rate_limit_cap(path: str, base_limit: int) -> int:
    if path in POLLING_RATE_LIMIT_PATHS:
        return max(base_limit * 5, 60)
    return base_limit


def create_app(*, lifespan: Callable, settings, route_timeouts: dict[str, int] | None = None) -> FastAPI:
    app = FastAPI(title="AlphaCore Quant Data Engine", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=settings.ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    rate_limit_db = defaultdict(list)
    app.state.rate_limit_db = rate_limit_db
    timeout_by_path = dict(DEFAULT_ROUTE_TIMEOUTS)
    if route_timeouts:
        timeout_by_path.update(route_timeouts)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        bucket = _rate_limit_bucket(client_ip, request.url.path)
        limit = _rate_limit_cap(request.url.path, settings.MAX_REQUESTS_PER_MINUTE)
        now = time.time()
        rate_limit_db[bucket] = [t for t in rate_limit_db[bucket] if now - t < 60]

        if len(rate_limit_db[bucket]) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests. Institutional API rate guard triggered."},
                headers={"Retry-After": "30"},
            )

        rate_limit_db[bucket].append(now)
        return await call_next(request)

    @app.middleware("http")
    async def timeout_middleware(request: Request, call_next):
        timeout = timeout_by_path.get(request.url.path, 25)
        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={
                    "error": f"Request timed out after {timeout}s",
                    "hint": "Check /api/health for source status or retry shortly.",
                },
            )

    return app


def mount_static_assets(app: FastAPI) -> None:
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
