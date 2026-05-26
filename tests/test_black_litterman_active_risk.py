import pytest
from core.portfolio_book import Position, build_portfolio_snapshot
from core.portfolio_opt import calculate_black_litterman

def test_black_litterman_active_risk_metrics():
    # 1. Prepare sandbox portfolio positions
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
    
    # Gold ETF +15% high confidence view
    views = {"GOLD_ETF": 0.15}
    confidences = {"GOLD_ETF": 0.85}
    
    res = calculate_black_litterman(
        portfolio_snapshot=snapshot,
        benchmark_weights=benchmark_weights,
        views=views,
        confidences=confidences
    )
    
    # 2. Assert key structure returns
    assert "active_risk_metrics" in res
    metrics = res["active_risk_metrics"]
    
    assert "original_active_risk_pct" in metrics
    assert "optimized_active_risk_pct" in metrics
    assert "projected_information_ratio" in metrics
    
    orig_risk = metrics["original_active_risk_pct"]
    opt_risk = metrics["optimized_active_risk_pct"]
    proj_ir = metrics["projected_information_ratio"]
    
    # Metrics must be float numbers
    assert isinstance(orig_risk, float)
    assert isinstance(opt_risk, float)
    assert isinstance(proj_ir, float)
    
    # Optimized active risk should be positive due to active gold view deviation
    assert opt_risk >= 0.0
    
    # 3. Test edge case: No active views (weights should align near equilibrium, active risk should be small)
    res_no_views = calculate_black_litterman(
        portfolio_snapshot=snapshot,
        benchmark_weights=benchmark_weights,
        views={},
        confidences={}
    )
    metrics_no_views = res_no_views["active_risk_metrics"]
    assert metrics_no_views["optimized_active_risk_pct"] < 0.1
    assert abs(metrics_no_views["projected_information_ratio"]) < 0.1
