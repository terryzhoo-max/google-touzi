import pytest
from core.portfolio_book import Position, build_portfolio_snapshot
from core.risk_engine import calculate_portfolio_risk

def test_liquidity_dtl_basic():
    # Megmeet 002851 has static ADV = 5,000,000 in STATIC_ADV_PROXY
    positions = [
        Position("002851", "Megmeet", "equity", "CNY", 150000.0, quantity=50000.0),
        Position("CASH", "Cash", "cash", "CNY", 100000.0, quantity=100000.0),
    ]
    snapshot = build_portfolio_snapshot(positions)
    
    risk = calculate_portfolio_risk(snapshot)
    assert "liquidity_metrics" in risk
    metrics = risk["liquidity_metrics"]
    
    # Megmeet quantity = 50000, ADV = 5,000,000.
    # DTL = 50000 / (5000000 * 0.1) = 0.1 days
    days = metrics["days_to_liquidate"]
    assert "002851" in days
    assert abs(days["002851"] - 0.1) < 1e-4
    assert days.get("CASH", 0.0) == 0.0  # Cash is infinite liquid
