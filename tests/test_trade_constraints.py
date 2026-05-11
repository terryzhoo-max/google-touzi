from core.trade_constraints import TradeConstraints, evaluate_trade_constraints


def test_trade_constraints_reject_excess_turnover_and_low_cash():
    result = evaluate_trade_constraints(
        target_weights={"SPY": 0.75, "TLT": 0.2, "GLD": 0.05, "CASH": 0.0},
        current_weights={"SPY": 0.45, "TLT": 0.25, "GLD": 0.15, "CASH": 0.15},
        constraints=TradeConstraints(max_turnover=0.2, min_cash_weight=0.05, max_position_weight=0.6),
    )

    assert result["passed"] is False
    assert "turnover_exceeded" in result["violations"]
    assert "cash_below_minimum" in result["violations"]
    assert "position_limit_exceeded:SPY" in result["violations"]


def test_trade_constraints_pass_conservative_rebalance():
    result = evaluate_trade_constraints(
        target_weights={"SPY": 0.35, "TLT": 0.25, "GLD": 0.2, "CASH": 0.2},
        current_weights={"SPY": 0.45, "TLT": 0.25, "GLD": 0.15, "CASH": 0.15},
        constraints=TradeConstraints(),
    )

    assert result["passed"] is True
    assert result["turnover"] == 0.1
    assert result["estimated_cost_bps"] == 1.0


def test_trade_constraints_do_not_require_cash_when_cash_is_not_in_portfolio():
    result = evaluate_trade_constraints(
        target_weights={"CSI300_ETF": 0.05, "GOLD_ETF": 0.95},
        current_weights={"CSI300_ETF": 0.1, "GOLD_ETF": 0.9},
        constraints=TradeConstraints(max_turnover=0.2, min_cash_weight=0.05, max_position_weight=1.0),
    )

    assert result["passed"] is True
