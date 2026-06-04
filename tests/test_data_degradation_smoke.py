import datetime
import time

import pandas as pd
from fastapi.testclient import TestClient

import app.routes.macro as macro_routes
import core.cache_store as cache_store
import core.data_providers as data_providers
import core.db_layer as db_layer
import core.global_assets as global_assets
import core.market_data as market_data
import core.valuation as valuation
import core.yield_curve as yield_curve
from data_engine import app


client = TestClient(app)


def _empty_series(name: str = "empty") -> pd.Series:
    return pd.Series(dtype=float, name=name)


def _reset_cache_store() -> None:
    cache_store._store.clear()
    cache_store._stats.update({"hits": 0, "misses": 0, "refreshes": 0, "stale_served": 0, "errors": 0})


def test_macro_routes_return_safe_payloads_when_external_sources_are_down(monkeypatch):
    today = datetime.date.today().strftime("%Y-%m-%d")

    def source_down(*args, **kwargs):
        raise OSError("upstream unavailable")

    monkeypatch.setattr(market_data.urllib.request, "urlopen", source_down)
    monkeypatch.setattr(data_providers, "_fred_series", lambda series_id, limit=60: _empty_series(series_id))
    monkeypatch.setattr(data_providers, "_tushare_items", lambda *args, **kwargs: [])
    monkeypatch.setattr(data_providers, "_akshare_fallback_enabled", lambda: False)
    monkeypatch.setattr(yield_curve, "_fred_series", lambda series_id, limit=60: _empty_series(series_id))
    monkeypatch.setattr(global_assets, "_fred_raw", lambda series_id, limit=60: _empty_series(series_id))
    monkeypatch.setattr(global_assets, "_tushare_items", lambda *args, **kwargs: [])
    monkeypatch.setattr(valuation, "_tushare_items", lambda *args, **kwargs: [])
    monkeypatch.setattr(macro_routes, "run_backtest", lambda: {"current_state": {}})
    monkeypatch.setattr(macro_routes, "calculate_correlation_matrix", lambda: {"matrix": []})
    monkeypatch.setattr(
        macro_routes,
        "get_yield_curve",
        lambda days=120: {
            "snapshot": {},
            "spread_dates": [],
            "spread_values": [],
            "inversion_days": 0,
            "signal_state": "No Data",
            "signal_color": "#94a3b8",
            "insight": "source unavailable",
        },
    )
    global_assets.LAST_SUCCESS.update({"data": None, "ts": 0, "errors": 0})
    valuation._last_ok.update({"data": None, "ts": 0, "errors": 0})

    endpoints = [
        "/api/macro/erp",
        "/api/macro/spread",
        "/api/macro/yield_curve",
        "/api/macro/decision",
        "/api/macro/global_assets",
        "/api/macro/valuation",
        "/api/macro/ai_insight",
    ]

    responses = {path: client.get(path) for path in endpoints}

    assert all(response.status_code == 200 for response in responses.values())
    assert responses["/api/macro/erp"].json()["data"] == [0.0]
    assert responses["/api/macro/spread"].json()["data"] == [0.0]
    assert "snapshot" in responses["/api/macro/yield_curve"].json()
    assert "score" in responses["/api/macro/decision"].json()
    assert responses["/api/macro/global_assets"].json()["updated"] == today
    assert responses["/api/macro/valuation"].json()["updated"] == today
    assert "insight" in responses["/api/macro/ai_insight"].json()


def test_route_cache_serves_stale_api_payload_when_refresh_fails(monkeypatch):
    _reset_cache_store()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(db_layer, "get_api_cache", lambda key: (None, 0))
    cache_store._store["erp"] = {
        "ts": time.time() - 1000,
        "ttl": 1,
        "value": {"signal_state": "cached-safe", "data": [4.0]},
    }
    monkeypatch.setattr(macro_routes, "fetch_market_data", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("FRED down")))

    response = client.get("/api/macro/erp")

    assert response.status_code == 200
    payload = response.json()
    assert payload["signal_state"] == "cached-safe"
    assert payload["_stale"] is True
    assert payload["_cache"]["key"] == "erp"
    assert payload["_cache"]["stale"] is True
