import pytest
from core.portfolio_book import Position, build_portfolio_snapshot
from core.portfolio_opt import calculate_black_litterman

def test_black_litterman_bayes():
    positions = [
        Position("SP500_ETF", "S&P 500 ETF", "equity", "USD", 300000.0),
        Position("GOLD_ETF", "Gold ETF", "gold", "CNY", 200000.0),
        Position("CASH", "Cash", "cash", "CNY", 100000.0),
    ]
    snapshot = build_portfolio_snapshot(positions)
    
    benchmark_weights = {
        "SP500_ETF": 0.60,
        "GOLD_ETF": 0.40,
    }
    
    # Subjective view: look up Gold by +10% with 90% confidence
    views = {"GOLD_ETF": 0.10}
    confidences = {"GOLD_ETF": 0.90}
    
    res = calculate_black_litterman(snapshot, benchmark_weights, views, confidences)
    
    assert "optimized_weights" in res
    assert "posterior_returns" in res
    assert "prior_returns" in res
    
    opt_w = res["optimized_weights"]
    # Gold weight should shift upwards
    assert opt_w["GOLD_ETF"] > 0.0
    assert "CASH" in opt_w
    # Cash weight must remain locked to 100k / 600k = 1/6
    assert abs(opt_w["CASH"] - 1.0/6.0) < 1e-4
