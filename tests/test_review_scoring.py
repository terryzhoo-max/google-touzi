from core.review_scoring import score_review


def test_score_review_marks_success_when_risk_improves_and_action_was_executable():
    result = score_review(
        audit_record={
            "ticket_id": "dt_abc",
            "payload": {
                "recommended_action": {"status": "staged_execution"},
                "what_if": {
                    "risk_delta": {"var_95_pct": 0.18, "worst_scenario_loss_pct": 1.1},
                    "constraints": {"passed": True},
                },
            },
        },
        review_window="T+1",
    )

    assert result["ticket_id"] == "dt_abc"
    assert result["review_window"] == "T+1"
    assert result["score"] == 90
    assert result["verdict"] == "effective"
    assert "risk_improved" in result["evidence"]


def test_score_review_marks_failed_when_action_blocked_or_risk_worsened():
    result = score_review(
        audit_record={
            "ticket_id": "dt_blocked",
            "payload": {
                "recommended_action": {"status": "blocked"},
                "what_if": {
                    "risk_delta": {"var_95_pct": -0.5, "worst_scenario_loss_pct": -2.0},
                    "constraints": {"passed": False},
                },
            },
        },
        review_window="T+5",
    )

    assert result["score"] == 20
    assert result["verdict"] == "ineffective"
    assert "constraints_failed" in result["evidence"]


def test_score_review_rewards_positive_attribution_effect():
    result = score_review(
        audit_record={
            "ticket_id": "dt_attr_positive",
            "payload": {
                "recommended_action": {"status": "staged_execution"},
                "attribution": {
                    "period": "T+5",
                    "decision_effect": 0.012,
                    "allocation_effect": 0.004,
                    "selection_effect": 0.008,
                    "currency_effect": 0.0,
                },
                "what_if": {
                    "risk_delta": {"var_95_pct": 0.1, "worst_scenario_loss_pct": 0.2},
                    "constraints": {"passed": True},
                },
            },
        },
        review_window="T+5",
    )

    assert result["score"] == 100
    assert result["attribution"]["decision_effect"] == 0.012
    assert "attribution_positive" in result["evidence"]
    assert "selection_positive" in result["evidence"]


def test_score_review_penalizes_negative_attribution_effect():
    result = score_review(
        audit_record={
            "ticket_id": "dt_attr_negative",
            "payload": {
                "recommended_action": {"status": "staged_execution"},
                "attribution": {
                    "period": "T+20",
                    "decision_effect": -0.009,
                    "allocation_effect": -0.004,
                    "selection_effect": -0.005,
                    "currency_effect": -0.001,
                },
                "what_if": {
                    "risk_delta": {"var_95_pct": 0.1, "worst_scenario_loss_pct": 0.2},
                    "constraints": {"passed": True},
                },
            },
        },
        review_window="T+20",
    )

    assert result["score"] == 78
    assert result["attribution"]["decision_effect"] == -0.009
    assert "attribution_negative" in result["evidence"]
    assert "currency_drag" in result["evidence"]
