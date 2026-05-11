from core.action_generator import generate_action_recommendation


def test_action_generator_recommends_staged_execution_when_what_if_improves_risk():
    recommendation = generate_action_recommendation(
        decision_ticket={
            "decision_status": "limited",
            "score": 83,
            "gates_failed": [],
        },
        what_if={
            "adjustments": {"SPY": -0.10, "GLD": 0.05, "CASH": 0.05},
            "risk_delta": {"var_95_pct": 0.18, "worst_scenario_loss_pct": 1.1},
            "constraints": {"passed": True, "violations": [], "turnover": 0.1},
            "improves_risk": True,
        },
    )

    assert recommendation["status"] == "staged_execution"
    assert recommendation["action"] == "Reduce SPY by 10.0%, add GLD by 5.0%, add CASH by 5.0%."
    assert recommendation["risk_improvement"] == "VaR improves by 0.18 pct points; worst scenario improves by 1.1 pct points."
    assert recommendation["requires_review"] is False


def test_action_generator_blocks_when_constraints_fail():
    recommendation = generate_action_recommendation(
        decision_ticket={
            "decision_status": "allow",
            "score": 90,
            "gates_failed": [],
        },
        what_if={
            "adjustments": {"SPY": 0.30, "CASH": -0.30},
            "risk_delta": {"var_95_pct": -0.5, "worst_scenario_loss_pct": -2.0},
            "constraints": {"passed": False, "violations": ["turnover_exceeded"]},
            "improves_risk": False,
        },
    )

    assert recommendation["status"] == "blocked"
    assert recommendation["requires_review"] is True
    assert "turnover_exceeded" in recommendation["rationale"]


def test_action_generator_blocks_when_pre_trade_compliance_blocks():
    recommendation = generate_action_recommendation(
        decision_ticket={
            "decision_status": "allow",
            "score": 90,
            "gates_failed": [],
        },
        what_if={
            "adjustments": {"NASDAQ_ETF": 0.05, "GOLD_ETF": -0.05},
            "risk_delta": {"var_95_pct": -0.1, "worst_scenario_loss_pct": -0.4},
            "constraints": {"passed": True, "violations": []},
            "compliance": {
                "status": "block",
                "violations": ["no_new_risk_when_risk_high"],
                "repair_suggestions": ["Reduce equity or technology exposure before adding risk."],
            },
            "improves_risk": False,
        },
    )

    assert recommendation["status"] == "blocked"
    assert "no_new_risk_when_risk_high" in recommendation["rationale"]
    assert "Reduce equity or technology exposure" in recommendation["risk_improvement"]
