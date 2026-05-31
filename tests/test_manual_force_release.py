import pytest
import os
import json
import builtins
from fastapi.testclient import TestClient
from data_engine import app
from core.db_layer import get_recent_trades

def test_execution_status_offline_when_missing(monkeypatch):
    orig_exists = os.path.exists
    def mock_exists(path):
        if "qmt_heartbeat.json" in str(path):
            return False
        return orig_exists(path)
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    client = TestClient(app)
    response = client.get("/api/institutional/execution/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "OFFLINE"
    assert payload["gateway_resilience_status"] == "NOT_RUNNING"
    assert payload["has_xtquant"] is False

def test_execution_status_online_when_exists(monkeypatch):
    test_data = {
        "status": "ONLINE",
        "gateway_resilience_status": "RUNNING",
        "has_xtquant": True,
        "dry_run": False,
        "retry_count": 0,
        "backoff_sec": 0,
        "timestamp": 1782635930.0
    }
    
    orig_exists = os.path.exists
    def mock_exists(path):
        if "qmt_heartbeat.json" in str(path):
            return True
        return orig_exists(path)
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    orig_open = builtins.open
    def mock_open(file, *args, **kwargs):
        if "qmt_heartbeat.json" in str(file):
            from io import StringIO
            return StringIO(json.dumps(test_data))
        return orig_open(file, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", mock_open)
    
    client = TestClient(app)
    response = client.get("/api/institutional/execution/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ONLINE"
    assert payload["gateway_resilience_status"] == "RUNNING"
    assert payload["has_xtquant"] is True
    assert payload["timestamp"] == 1782635930.0

def test_force_release_auth_failure():
    client = TestClient(app)
    response = client.post(
        "/api/institutional/execution/force_release",
        json={
            "auth_key": "WRONG_KEY",
            "symbol": "510300",
            "side": "BUY",
            "quantity": 1000,
            "limit_price": 3.25,
            "execution_algo": "DIRECT"
        }
    )
    assert response.status_code == 403
    assert "Invalid CCO authorization key" in response.json()["detail"]

def test_force_release_success_and_db_persistence(monkeypatch):
    from core.config import settings
    monkeypatch.setattr(settings, "CCO_AUTH_KEY", "TestCCOKey2026")
    
    client = TestClient(app)
    portfolio_id = "test_force_release_portfolio"
    
    response = client.post(
        "/api/institutional/execution/force_release",
        json={
            "auth_key": "TestCCOKey2026",
            "symbol": "510300.SH",
            "side": "BUY",
            "quantity": 1500,
            "limit_price": 3.42,
            "execution_algo": "TWAP",
            "portfolio_id": portfolio_id
        }
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    order_id = payload["order_id"]
    assert order_id.startswith("cco_force_")
    
    # Query database and verify persistence
    trades = get_recent_trades(limit=10, portfolio_id=portfolio_id)
    assert len(trades) > 0
    
    target_trade = next((t for t in trades if t["order_id"] == order_id), None)
    assert target_trade is not None
    assert target_trade["symbol"] == "510300.SH"
    assert target_trade["side"] == "BUY"
    assert target_trade["quantity"] == 1500
    assert target_trade["limit_price"] == 3.42
    assert target_trade["status"] == "PENDING"
