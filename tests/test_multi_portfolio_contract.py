import pytest
from fastapi.testclient import TestClient
from data_engine import app

def test_global_risk_net_contract():
    client = TestClient(app)
    response = client.get("/api/institutional/global_risk_net")
    assert response.status_code == 200
    
    payload = response.json()
    assert "total_market_value" in payload
    assert "joint_scenarios" in payload
    assert "portfolio_contributions" in payload
    assert "worst_scenario" in payload
    assert "global_status" in payload
    
    # Check default status
    assert payload["global_status"] in {"NORMAL", "CROSS_PORTFOLIO_WARNING"}
    
    # Confirm contributions detail
    contribs = payload["portfolio_contributions"]
    assert len(contribs) > 0
    for c in contribs:
        assert "portfolio_name" in c
        assert "weight_pct" in c
        assert "worst_scenario_loss_pct" in c
        assert "worst_scenario_name" in c

def test_global_risk_net_sentinel_warning(monkeypatch):
    # Mock run_global_risk_net to return a worst scenario loss of -15.0%
    import core.scenario_engine
    
    original_run = core.scenario_engine.run_global_risk_net
    
    def mocked_run(snapshots):
        res = original_run(snapshots)
        if "worst_scenario" in res:
            res["worst_scenario"]["portfolio_loss_pct"] = -15.0
        return res
        
    monkeypatch.setattr(core.scenario_engine, "run_global_risk_net", mocked_run)
    
    client = TestClient(app)
    response = client.get("/api/institutional/global_risk_net")
    assert response.status_code == 200
    payload = response.json()
    assert payload["global_status"] == "CROSS_PORTFOLIO_WARNING"
    assert payload["worst_scenario"]["portfolio_loss_pct"] == -15.0
