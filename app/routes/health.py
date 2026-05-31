import os

from fastapi import APIRouter, FastAPI

from core.alert_state import get_active_alerts
from core.cache_store import ROUTE_TTL, get_cache_stats
from core.data_providers import get_circuit_state, get_provider_stats
from core.runtime_diagnostics import build_runtime_diagnostics


def register_health_routes(app: FastAPI, *, settings, rate_limit_db) -> None:
    router = APIRouter()

    @router.get("/api/health")
    def api_health():
        ps = get_provider_stats()
        circuit = get_circuit_state()
        degraded = [
            k
            for k, v in ps.items()
            if v.get("error_rate", 0) > 0.3 or circuit.get(k, {"state": "closed"}).get("state") != "closed"
        ]
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
                "tracked_clients": len(rate_limit_db),
            },
            "active_alerts": len(get_active_alerts()),
            "routes": list(ROUTE_TTL.keys()),
        }

    app.include_router(router)
