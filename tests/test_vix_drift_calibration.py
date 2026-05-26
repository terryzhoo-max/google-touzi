import pytest
from core.scenario_engine import run_historical_replication_analysis

def test_vix_drift_impact():
    """Verify that higher VIX drift term scales early-stage historical shocks accordingly."""
    portfolio_snapshot = {
        "total_market_value": 1000000.0,
        "positions": [
            {"symbol": "510300.SH", "weight": 0.80, "market_value": 800000.0, "asset_class": "equity"},
            {"symbol": "CASH", "weight": 0.20, "market_value": 200000.0, "asset_class": "cash"}
        ]
    }
    
    benchmark_weights = {"510300.SH": 1.0}
    risk_parity_weights = {"510300.SH": 0.5, "CASH": 0.5}
    
    # 1. Base case: VIX = 20.0 (normal)
    res_base = run_historical_replication_analysis(
        portfolio_snapshot,
        benchmark_weights,
        risk_parity_weights,
        vix=20.0
    )
    
    # 2. Stressed case: VIX = 40.0 (high)
    res_stressed = run_historical_replication_analysis(
        portfolio_snapshot,
        benchmark_weights,
        risk_parity_weights,
        vix=40.0
    )
    
    # Maximum drawdowns under covid_2020 should scale and show higher impact under high VIX
    base_mdd = abs(res_base["covid_2020"]["max_drawdowns"]["portfolio_pct"])
    stressed_mdd = abs(res_stressed["covid_2020"]["max_drawdowns"]["portfolio_pct"])
    
    assert stressed_mdd >= base_mdd
