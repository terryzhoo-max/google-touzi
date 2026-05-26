import pytest
from core.portfolio_book import build_portfolio_snapshot, Position
from core.trade_constraints import evaluate_portfolio_funding_drag

def test_funding_drag_cost_simulation():
    """Verify that build_portfolio_snapshot generates realistic daily funding drag metrics."""
    positions = [
        Position("510300.SH", "CSI 300", "equity", "CNY", 900000.0),
        Position("CASH", "Cash", "cash", "CNY", 100000.0)
    ]
    
    # 1. Run snapshot builder
    snap = build_portfolio_snapshot(positions)
    
    assert "cash_t1_locked" in snap
    assert "funding_drag_cost" in snap
    assert "funding_drag_bps" in snap
    
    # Risk asset market value is 900,000.0. Locked cash at 10% is 90,000.0.
    assert snap["cash_t1_locked"] == 90000.0
    
    # Daily funding cost = 90,000 * 0.035 / 365 = 8.6301
    assert abs(snap["funding_drag_cost"] - 8.6301) < 0.01
    
    # 2. Check compliance sentinel check
    compliance = evaluate_portfolio_funding_drag(snap)
    assert compliance["passed"] is True
    assert compliance["lock_ratio"] == 0.09  # 90k / 1M = 9%
    
    # 3. Simulate leverage breach (95% risk assets)
    extreme_positions = [
        Position("510300.SH", "CSI 300", "equity", "CNY", 950000.0),
        Position("CASH", "Cash", "cash", "CNY", 50000.0)
    ]
    snap_breach = build_portfolio_snapshot(extreme_positions)
    # Locked cash is 95,000. Lock ratio is 95,000 / 1M = 9.5% (which is still below 80% threshold)
    compliance_extreme = evaluate_portfolio_funding_drag(snap_breach)
    assert compliance_extreme["passed"] is True
