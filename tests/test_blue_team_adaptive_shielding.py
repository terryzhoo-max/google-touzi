import pytest
from core.scenario_engine import run_historical_replication_analysis

def test_blue_team_shielding_drawdown_control():
    """Verify that Blue-Team Defense Portfolio outperforms static Buy-and-Hold on extreme shocks."""
    portfolio_snapshot = {
        "total_market_value": 1000000.0,
        "positions": [
            {"symbol": "510300.SH", "weight": 0.90, "market_value": 900000.0, "asset_class": "equity"},
            {"symbol": "CASH", "weight": 0.10, "market_value": 1000000.0, "asset_class": "cash"}
        ]
    }
    
    benchmark_weights = {"510300.SH": 1.0}
    risk_parity_weights = {"510300.SH": 0.5, "CASH": 0.5}
    
    # 1. Run dynamic时序推演 (high VIX = 50.0 to guarantee drawdown > 5% trigger)
    res = run_historical_replication_analysis(
        portfolio_snapshot,
        benchmark_weights,
        risk_parity_weights,
        vix=50.0
    )
    
    # Check lehman_2008
    lehman = res["lehman_2008"]
    nav_port = lehman["portfolio_nav"]
    nav_blue = lehman["blue_team_defense_nav"]
    
    assert len(nav_port) == 31
    assert len(nav_blue) == 31
    
    mdds = lehman["max_drawdowns"]
    port_dd = mdds["portfolio_pct"]
    blue_dd = mdds["blue_team_defense_pct"]
    
    # AI Blue team defense should mitigate maximum drawdown significantly compared to B&H
    assert abs(blue_dd) <= abs(port_dd)
    assert "survival_alpha_pct" in mdds
    assert mdds["survival_alpha_pct"] >= 0.0
