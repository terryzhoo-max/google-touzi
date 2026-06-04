import sqlite3
import time

import core.cache_store as cache_store
import core.db_layer as db_layer
from core.cache_store import cached, make_cache_key


def _init_api_cache_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_cache (
            endpoint_key TEXT PRIMARY KEY,
            payload_json TEXT,
            updated_at REAL
        )
        """
    )
    conn.commit()
    conn.close()


def _reset_route_cache():
    cache_store._store.clear()
    cache_store._stats.update({"hits": 0, "misses": 0, "refreshes": 0, "stale_served": 0, "errors": 0})


def test_cache_key_includes_portfolio_and_period_dimensions():
    assert (
        make_cache_key(
            "institutional_attribution",
            {"portfolio": "institutional_portfolio", "period": "T-1"},
        )
        == "institutional_attribution_institutional_portfolio_T-1"
    )


def test_cache_key_keeps_periods_isolated_for_default_portfolio():
    t1 = make_cache_key("institutional_attribution", {"period": "T-1", "portfolio": None})
    t5 = make_cache_key("institutional_attribution", {"period": "T-5", "portfolio": None})

    assert t1 == "institutional_attribution_T-1"
    assert t5 == "institutional_attribution_T-5"
    assert t1 != t5


def test_cached_route_returns_fresh_l1_payload_with_cache_metadata(monkeypatch):
    _reset_route_cache()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    cache_store._store["unit_route"] = {
        "ts": time.time(),
        "ttl": 300,
        "value": {"status": "ok"},
    }

    @cached(ttl=300, key="unit_route")
    def route():
        raise AssertionError("fresh L1 should bypass route body")

    result = route()

    assert result["status"] == "ok"
    assert result["_cache"]["key"] == "unit_route"
    assert result["_cache"]["stale"] is False


def test_cached_route_serves_stale_l1_when_refresh_fails(monkeypatch):
    _reset_route_cache()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    cache_store._store["unit_stale"] = {
        "ts": time.time() - 1000,
        "ttl": 1,
        "value": {"status": "previous"},
    }

    @cached(ttl=1, key="unit_stale")
    def route():
        raise RuntimeError("provider down")

    result = route()

    assert result["status"] == "previous"
    assert result["_cache"]["stale"] is True
    assert result["_stale"] is True


def test_cached_route_rehydrates_from_sqlite_l2(monkeypatch, tmp_path):
    _reset_route_cache()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    db_path = tmp_path / "cache.db"
    _init_api_cache_db(db_path)
    monkeypatch.setattr(db_layer, "DB_PATH", str(db_path))
    db_layer.save_api_cache("unit_l2", {"status": "from-db"})

    @cached(ttl=300, key="unit_l2")
    def route():
        raise AssertionError("fresh L2 should bypass route body")

    result = route()

    assert result["status"] == "from-db"
    assert result["_cache"]["key"] == "unit_l2"
    assert "unit_l2" in cache_store._store


def test_get_api_cache_ignores_corrupted_json(monkeypatch, tmp_path):
    db_path = tmp_path / "cache.db"
    _init_api_cache_db(db_path)
    monkeypatch.setattr(db_layer, "DB_PATH", str(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO api_cache (endpoint_key, payload_json, updated_at) VALUES (?, ?, ?)",
        ("bad", "{not-json", time.time()),
    )
    conn.commit()
    conn.close()

    assert db_layer.get_api_cache("bad") == (None, 0.0)


def test_invalidate_deletes_only_requested_cache_key(monkeypatch, tmp_path):
    _reset_route_cache()
    db_path = tmp_path / "cache.db"
    _init_api_cache_db(db_path)
    monkeypatch.setattr(db_layer, "DB_PATH", str(db_path))
    cache_store._store["keep"] = {"ts": time.time(), "ttl": 300, "value": {"value": 1}}
    cache_store._store["drop"] = {"ts": time.time(), "ttl": 300, "value": {"value": 2}}
    db_layer.save_api_cache("keep", {"value": 1})
    db_layer.save_api_cache("drop", {"value": 2})

    cache_store.invalidate("drop")

    keep, _ = db_layer.get_api_cache("keep")
    drop, _ = db_layer.get_api_cache("drop")
    assert keep == {"value": 1}
    assert drop is None
    assert "keep" in cache_store._store
    assert "drop" not in cache_store._store


def test_cached_route_does_not_store_empty_error_payload(monkeypatch, tmp_path):
    _reset_route_cache()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    db_path = tmp_path / "cache.db"
    _init_api_cache_db(db_path)
    monkeypatch.setattr(db_layer, "DB_PATH", str(db_path))
    calls = {"count": 0}

    @cached(ttl=300, key="unit_error")
    def route():
        calls["count"] += 1
        return {
            "dates": ["Error"],
            "data": [0.0],
            "signal_state": "无数据",
            "signal_color": "#94a3b8",
            "action_insight": "无法连接至数据源。",
        }

    first = route()

    deadline = time.time() + 2
    while calls["count"] == 0 and time.time() < deadline:
        time.sleep(0.01)

    cached_payload, _ = db_layer.get_api_cache("unit_error")
    assert first["status"] == "syncing"
    assert calls["count"] == 1
    assert "unit_error" not in cache_store._store
    assert cached_payload is None
