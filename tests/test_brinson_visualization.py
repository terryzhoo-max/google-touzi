import pytest
from fastapi.testclient import TestClient
from data_engine import app

def test_brinson_attribution_default_portfolio():
    client = TestClient(app)
    response = client.get("/api/institutional/attribution")
    assert response.status_code == 200
    
    payload = response.json()
    assert "portfolio_return" in payload
    assert "benchmark_return" in payload
    assert "active_return" in payload
    assert "allocation_effect" in payload
    assert "selection_effect" in payload
    assert "interaction_effect" in payload
    assert "by_class" in payload
    
    # Verify the algebraic identity: Active Return = Allocation + Selection + Interaction
    p_ret = payload["portfolio_return"]
    b_ret = payload["benchmark_return"]
    act_ret = payload["active_return"]
    alloc = payload["allocation_effect"]
    select = payload["selection_effect"]
    inter = payload["interaction_effect"]
    
    assert abs(act_ret - (p_ret - b_ret)) < 1e-6
    assert abs(act_ret - (alloc + select + inter)) < 1e-4

def test_brinson_attribution_parameters():
    client = TestClient(app)
    # Test different periods and portfolios
    periods = ["T-1", "T+1", "T+5", "T+20"]
    portfolios = ["tactical_hedged_portfolio", None]
    
    for period in periods:
        for port in portfolios:
            params = {"period": period}
            if port:
                params["portfolio"] = port
                
            response = client.get("/api/institutional/attribution", params=params)
            assert response.status_code == 200
            payload = response.json()
            assert payload["period"] == period
            assert len(payload["by_class"]) > 0
            
            # Check fields inside each asset class
            for item in payload["by_class"]:
                assert "asset_class" in item
                assert "portfolio_weight" in item
                assert "benchmark_weight" in item
                assert "portfolio_return" in item
                assert "benchmark_return" in item
                assert "allocation_effect" in item
                assert "selection_effect" in item
                assert "interaction_effect" in item
                assert "active_return" in item
