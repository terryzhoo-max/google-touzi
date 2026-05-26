import pytest
from core.scenario_engine import run_global_risk_net

def test_run_global_risk_net_calculation():
    """Verify that joint stress testing combines weights and outputs valid metrics."""
    snap1 = {
        "total_market_value": 1000000.0,
        "display_name": "Core Alpha Portfolio",
        "positions": [
            {"symbol": "510300.SH", "weight": 0.60, "market_value": 600000.0, "asset_class": "equity"},
            {"symbol": "CASH", "weight": 0.40, "market_value": 400000.0, "asset_class": "cash"}
        ]
    }
    
    snap2 = {
        "total_market_value": 2000000.0,
        "display_name": "Global Hedged Portfolio",
        "positions": [
            {"symbol": "510500.SH", "weight": 0.50, "market_value": 1000000.0, "asset_class": "equity"},
            {"symbol": "CASH", "weight": 0.50, "market_value": 1000000.0, "asset_class": "cash"}
        ]
    }
    
    # 1. Run joint risk analysis
    res = run_global_risk_net([snap1, snap2])
    
    assert res["total_market_value"] == 3000000.0
    assert len(res["joint_scenarios"]) > 0
    assert "portfolio_contributions" in res
    
    # Confirm contributions
    contribs = res["portfolio_contributions"]
    assert len(contribs) == 2
    
    weights = {c["portfolio_name"]: c["weight_pct"] for c in contribs}
    assert weights["Core Alpha Portfolio"] == 33.33
    assert weights["Global Hedged Portfolio"] == 66.67
    
    # Confirm worst scenario exists
    assert res["worst_scenario"] is not None
    assert "portfolio_loss_pct" in res["worst_scenario"]
