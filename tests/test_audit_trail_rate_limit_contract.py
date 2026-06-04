from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.factory import create_app
from app.routes.audit import register_audit_routes


ROOT = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def _lifespan(app):
    yield


def _test_app(max_requests_per_minute: int = 3):
    settings = SimpleNamespace(
        ALLOWED_ORIGINS=[],
        ALLOW_CREDENTIALS=False,
        MAX_REQUESTS_PER_MINUTE=max_requests_per_minute,
    )
    app = create_app(lifespan=_lifespan, settings=settings)

    @app.get("/api/audit_trail")
    def audit_trail():
        return {"trades": []}

    @app.get("/api/protected")
    def protected():
        return {"ok": True}

    return app


def _audit_route_app():
    settings = SimpleNamespace(
        ALLOWED_ORIGINS=[],
        ALLOW_CREDENTIALS=False,
        MAX_REQUESTS_PER_MINUTE=20,
    )
    app = create_app(lifespan=_lifespan, settings=settings)
    register_audit_routes(app, build_payload=lambda portfolio=None: {})
    return app


def test_audit_trail_polling_does_not_exhaust_core_api_rate_limit():
    with TestClient(_test_app(max_requests_per_minute=3)) as client:
        for _ in range(5):
            assert client.get("/api/audit_trail").status_code == 200

        assert client.get("/api/protected").status_code == 200
        assert client.get("/api/protected").status_code == 200
        assert client.get("/api/protected").status_code == 200
        assert client.get("/api/protected").status_code == 429


def test_audit_trail_frontend_uses_backoff_not_fixed_3s_polling():
    js = (ROOT / "static" / "js" / "panels" / "audit_trail.js").read_text(encoding="utf-8")
    execution_js = (ROOT / "static" / "js" / "panels" / "execution_monitor.js").read_text(encoding="utf-8")
    api_js = (ROOT / "static" / "js" / "core" / "api.js").read_text(encoding="utf-8")
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    assert "setInterval(window.refreshAuditTrail, 3000)" not in js
    assert "setInterval(window.syncExecutionMonitor" not in execution_js
    assert "AUDIT_TRAIL_REFRESH_MS = 10000" in js
    assert "auditTrailState.inFlight" in js
    assert "auditTrailPollerId" in js
    assert "AUDIT_TRAIL_LEADER_KEY" in js
    assert "BroadcastChannel" in js
    assert "auditTrailTryBecomeLeader" in js
    assert "AlphaCore.api.originalFetch" in js
    assert "fetchAuditTrailResponse" in api_js
    assert "isAuditTrailRequest" in api_js
    assert "renderExecutionMonitorFromAuditTrail" in execution_js
    assert "Retry-After" in js
    assert "js/core/api.js?v=2" in html
    assert "js/panels/audit_trail.js?v=4" in html
    assert "js/panels/execution_monitor.js?v=3" in html


def test_audit_trail_route_sets_short_browser_cache_header():
    with TestClient(_audit_route_app()) as client:
        response = client.get("/api/audit_trail")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, max-age=10, stale-while-revalidate=20"


def test_audit_trail_route_uses_server_side_short_cache(monkeypatch):
    import app.routes.audit as audit_routes
    import core.db_layer as db_layer

    audit_routes._audit_trail_cache.clear()
    calls = []

    def fake_recent_trades(limit=50, portfolio_id=None):
        calls.append((limit, portfolio_id))
        return [{"order_id": f"order-{len(calls)}"}]

    monkeypatch.setattr(db_layer, "get_recent_trades", fake_recent_trades)

    with TestClient(_audit_route_app()) as client:
        first = client.get("/api/audit_trail?limit=15")
        second = client.get("/api/audit_trail?limit=15")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert calls == [(15, None)]
