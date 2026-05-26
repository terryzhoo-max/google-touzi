from fastapi.testclient import TestClient
from data_engine import app

client = TestClient(app)

def test_api_commit_custom_decision_bayesian():
    # Test Black-Litterman rebalance commit
    payload = {
        "source": "bayesian_rebalance",
        "portfolio": "tactical_hedged_portfolio",
        "views": {"SPY": 0.05, "GLD": -0.02},
        "confidences": {"SPY": 0.8, "GLD": 0.5}
    }
    
    response = client.post("/api/institutional/audit/commit_custom", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert "ticket_id" in res_data
    assert res_data["ticket_id"].startswith("dt_")
    
    # Verify the record exists in the audit trail database and payload has views
    ticket_id = res_data["ticket_id"]
    loaded = client.get(f"/api/institutional/audit/decisions/{ticket_id}").json()
    assert loaded["ticket_id"] == ticket_id
    assert "views" in loaded["payload"]
    assert loaded["payload"]["views"]["SPY"] == 0.05
    assert loaded["payload"]["confidences"]["GLD"] == 0.5

def test_api_commit_custom_decision_shock():
    # Test Custom Shock Sandbox commit
    payload = {
        "source": "macro_shock_sandbox",
        "portfolio": "tactical_hedged_portfolio",
        "shocks": {
            "equity_shock": -25.0,
            "rate_shock": 5.0,
            "vol_shock": 3.0,
            "commodity_shock": 2.0
        }
    }
    
    response = client.post("/api/institutional/audit/commit_custom", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert "ticket_id" in res_data
    assert res_data["ticket_id"].startswith("dt_")
    
    ticket_id = res_data["ticket_id"]
    loaded = client.get(f"/api/institutional/audit/decisions/{ticket_id}").json()
    assert loaded["ticket_id"] == ticket_id
    assert "shocks" in loaded["payload"]
    assert loaded["payload"]["shocks"]["equity_shock"] == -25.0
    assert loaded["payload"]["shocks"]["commodity_shock"] == 2.0
