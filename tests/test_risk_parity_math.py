import pytest
import numpy as np
from core.portfolio_opt import solve_risk_parity, calculate_risk_parity_allocation
from core.portfolio_book import Position, build_portfolio_snapshot

def test_convex_risk_parity_solver_proportionality():
    # 1. Setup a realistic positive-definite covariance matrix
    # 3 assets (e.g., SPY, TLT, GLD)
    vol = np.array([0.15, 0.08, 0.12])
    corr = np.array([
        [1.0, -0.2, 0.1],
        [-0.2, 1.0, 0.2],
        [0.1, 0.2, 1.0]
    ])
    cov = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            cov[i, j] = corr[i, j] * vol[i] * vol[j]
            
    # 2. Run test under Equal Risk Parity (budgets = 1/3)
    budgets_equal = np.array([1.0/3, 1.0/3, 1.0/3])
    w_opt_equal = solve_risk_parity(cov, budgets_equal)
    
    # Assert weights sum to 1.0 and are positive
    assert len(w_opt_equal) == 3
    assert abs(w_opt_equal.sum() - 1.0) < 1e-6
    assert np.all(w_opt_equal > 0.0)
    
    # Calculate ACTR (Absolute Contribution to Risk) under optimized weights
    port_vol = np.sqrt(np.dot(w_opt_equal.T, np.dot(cov, w_opt_equal)))
    mctr = np.dot(cov, w_opt_equal) / port_vol
    actr = w_opt_equal * mctr
    actr_pct = actr / actr.sum()
    
    # Assert ACTR percentage strictly matches equal risk budgets
    for i in range(3):
        assert abs(actr_pct[i] - budgets_equal[i]) < 1e-4
        
    # 3. Run test under Custom Risk Budgeting (e.g. 50% SPY, 30% TLT, 20% GLD)
    budgets_custom = np.array([0.5, 0.3, 0.2])
    w_opt_custom = solve_risk_parity(cov, budgets_custom)
    
    assert abs(w_opt_custom.sum() - 1.0) < 1e-6
    assert np.all(w_opt_custom > 0.0)
    
    port_vol_custom = np.sqrt(np.dot(w_opt_custom.T, np.dot(cov, w_opt_custom)))
    mctr_custom = np.dot(cov, w_opt_custom) / port_vol_custom
    actr_custom = w_opt_custom * mctr_custom
    actr_pct_custom = actr_custom / actr_custom.sum()
    
    # Assert ACTR percentage strictly matches custom risk budgets
    for i in range(3):
        assert abs(actr_pct_custom[i] - budgets_custom[i]) < 1e-4


def test_calculate_risk_parity_allocation_integration():
    portfolio = build_portfolio_snapshot([
        Position("SP500_ETF", "SPY", "equity", "USD", 500.0, region="US", strategy="broad_market"),
        Position("GOLD_ETF", "Gold", "gold", "CNY", 300.0, region="Gold", strategy="gold"),
        Position("CASH", "Cash USD", "cash", "USD", 200.0, region="Global", strategy="cash"),
    ])
    
    benchmark_weights = {
        "SP500_ETF": 0.6,
        "GOLD_ETF": 0.4
    }
    
    # Custom budgets: 60% risk to SPY, 40% risk to Gold
    budgets = {
        "SP500_ETF": 0.6,
        "GOLD_ETF": 0.4
    }
    
    res = calculate_risk_parity_allocation(portfolio, benchmark_weights, budgets)
    
    assert "optimized_weights" in res
    assert "benchmark_weights" in res
    assert "risk_parity_details" in res
    assert res["portfolio_volatility_pct"] > 0
    
    # Verify CASH weight is kept constant at 20%
    assert abs(res["optimized_weights"]["CASH"] - 0.2) < 1e-5
    assert abs(res["benchmark_weights"]["CASH"] - 0.2) < 1e-5
    
    # Verify remaining weights sum to 80%
    assert abs(res["optimized_weights"]["SP500_ETF"] + res["optimized_weights"]["GOLD_ETF"] - 0.8) < 1e-5
    
    # Verify ACTR in details matches the specified budgets
    spy_actr_pct = res["risk_parity_details"]["SP500_ETF"]["actual_risk_contribution_pct"]
    gold_actr_pct = res["risk_parity_details"]["GOLD_ETF"]["actual_risk_contribution_pct"]
    assert abs(spy_actr_pct - 60.0) < 1e-2
    assert abs(gold_actr_pct - 40.0) < 1e-2


def test_risk_parity_empty_portfolio_fallback():
    # Empty portfolio snapshot
    portfolio = {"positions": [], "total_market_value": 0.0}
    res = calculate_risk_parity_allocation(portfolio, {})
    assert res["optimized_weights"] == {}
    assert res["portfolio_volatility_pct"] == 0.0
