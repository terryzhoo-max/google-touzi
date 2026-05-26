import pytest
import math
from core.scenario_engine import get_historical_crisis_factor_series, run_historical_replication_analysis
from core.portfolio_book import Position, build_portfolio_snapshot

def test_historical_crisis_series_structure():
    # 1. Test factor time-series generator
    crises = ["lehman_2008", "covid_2020", "taper_2013", "stagflation_1970"]
    for cid in crises:
        shocks = get_historical_crisis_factor_series(cid, days=30)
        assert len(shocks) == 30
        for shock in shocks:
            assert "equity_beta" in shock
            assert "liquidity_sensitivity" in shock
            assert "dollar_sensitivity" in shock
            assert "rate_sensitivity" in shock
            assert "inflation_sensitivity" in shock
            
            # Shocks should be floats and within reasonable macro bounds
            for k, val in shock.items():
                assert isinstance(val, float)
                assert -0.2 < val < 0.2


def test_historical_replication_nav_and_drawdown_algebraic_soundness():
    portfolio = build_portfolio_snapshot([
        Position("SP500_ETF", "SPY", "equity", "USD", 600.0, region="US", strategy="broad_market"),
        Position("GOLD_ETF", "Gold", "gold", "CNY", 400.0, region="Gold", strategy="gold"),
    ])
    
    benchmark_weights = {
        "SP500_ETF": 0.5,
        "GOLD_ETF": 0.5
    }
    
    risk_parity_weights = {
        "SP500_ETF": 0.35,
        "GOLD_ETF": 0.65
    }
    
    res = run_historical_replication_analysis(portfolio, benchmark_weights, risk_parity_weights)
    
    # Assert output structure is correct for all 4 crises
    assert "lehman_2008" in res
    assert "covid_2020" in res
    assert "taper_2013" in res
    assert "stagflation_1970" in res
    
    for cid, data in res.items():
        assert "dates" in data
        assert "portfolio_nav" in data
        assert "benchmark_nav" in data
        assert "risk_parity_nav" in data
        assert "max_drawdowns" in data
        
        # Verify length of NAV paths (D0 + 30 days = 31 data points)
        assert len(data["dates"]) == 31
        assert len(data["portfolio_nav"]) == 31
        assert len(data["benchmark_nav"]) == 31
        assert len(data["risk_parity_nav"]) == 31
        
        # Verify initial values are strictly 1.0
        assert data["portfolio_nav"][0] == 1.0
        assert data["benchmark_nav"][0] == 1.0
        assert data["risk_parity_nav"][0] == 1.0
        
        # Verify cumulative multiplication soundness (each NAV point is positive)
        for nav in data["portfolio_nav"]:
            assert nav > 0.0
            
        # Verify max drawdown calculation is algebraic and negative (or 0)
        dd = data["max_drawdowns"]
        assert dd["portfolio_pct"] <= 0.0
        assert dd["benchmark_pct"] <= 0.0
        assert dd["risk_parity_pct"] <= 0.0
        
        # Reduction Alpha must be exactly equivalent to portfolio MaxDD - RiskParity MaxDD
        expected_alpha = round(dd["portfolio_pct"] - dd["risk_parity_pct"], 2)
        assert abs(dd["drawdown_reduction_alpha_pct"] - expected_alpha) < 1e-5
