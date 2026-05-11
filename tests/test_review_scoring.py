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
