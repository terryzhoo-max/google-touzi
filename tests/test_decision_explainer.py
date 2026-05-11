from core.decision_explainer import build_decision_explanation


def test_decision_explainer_builds_audit_ready_reason_codes():
    explanation = build_decision_explanation(
        decision_ticket={
            "decision_status": "limited",
            "score": 83,
            "gates_failed": [],
        },
        data_quality={"score": 96, "status": "strong", "flags": []},
        risk={
            "risk_level": "medium",
            "var_95_pct": -1.26,
            "risk_contribution": {"equity": 0.97, "gold": 0.03},
        },
        scenarios={
            "worst_scenario": {
                "id": "equity_liquidity_shock",
                "name": "Equity liquidity shock",
                "portfolio_loss_pct": -7.0,
            }
        },
        portfolio={
            "region_exposure": {"China": 0.444444, "US": 0.222222},
            "strategy_exposure": {"technology": 0.444444, "broad_market": 0.222222},
            "asset_class_exposure": {"equity": 0.888889, "gold": 0.111111},
            "concentration_level": "low",
        },
        what_if={
            "improves_risk": True,
            "risk_delta": {"var_95_pct": 0.08, "worst_scenario_loss_pct": 0.75},
            "constraints": {"passed": True, "violations": []},
        },
        recommended_action={"status": "staged_execution"},
    )

    codes = [item["code"] for item in explanation["reason_codes"]]

    assert explanation["execution_readiness"] == "executable_with_review"
    assert explanation["primary_driver"]["code"] == "scenario_loss_watch"
    assert "portfolio_technology_exposure" in codes
    assert "portfolio_china_exposure" in codes
    assert "what_if_improves_risk" in codes
    assert explanation["supporting_evidence"]["data_quality_score"] == 96
    assert explanation["supporting_evidence"]["worst_scenario_id"] == "equity_liquidity_shock"
    assert explanation["policy_version"] == "institutional_policy_v1"
    assert len(explanation["policy_hash"]) == 64
    assert explanation["supporting_evidence"]["policy_version"] == "institutional_policy_v1"
    assert explanation["supporting_evidence"]["policy_hash"] == explanation["policy_hash"]
    assert explanation["review_focus"] == [
        "stress loss path",
        "technology exposure",
        "China exposure",
    ]


def test_decision_explainer_marks_blocked_constraints_as_primary_driver():
    explanation = build_decision_explanation(
        decision_ticket={
            "decision_status": "allow",
            "score": 90,
            "gates_failed": [],
        },
        data_quality={"score": 100, "status": "strong", "flags": []},
        risk={"risk_level": "low", "var_95_pct": -0.7, "risk_contribution": {}},
        scenarios={"worst_scenario": {"id": "rate_shock", "portfolio_loss_pct": -2.0}},
        portfolio={"strategy_exposure": {}, "region_exposure": {}, "asset_class_exposure": {}},
        what_if={
            "improves_risk": False,
            "risk_delta": {"var_95_pct": -0.2},
            "constraints": {"passed": False, "violations": ["turnover_exceeded"]},
        },
        recommended_action={"status": "blocked"},
    )

    assert explanation["execution_readiness"] == "blocked"
    assert explanation["primary_driver"]["code"] == "constraint_turnover_exceeded"
    assert explanation["review_focus"] == ["constraint breach"]


def test_decision_explainer_deduplicates_gate_and_model_reason_codes():
    explanation = build_decision_explanation(
        decision_ticket={
            "decision_status": "observe",
            "score": 58,
            "gates_failed": ["scenario_loss_high"],
        },
        data_quality={"score": 100, "status": "strong", "flags": []},
        risk={"risk_level": "medium", "var_95_pct": -1.2, "risk_contribution": {}},
        scenarios={
            "worst_scenario": {
                "id": "equity_liquidity_shock",
                "portfolio_loss_pct": -13.33,
            }
        },
        portfolio={"strategy_exposure": {}, "region_exposure": {}, "asset_class_exposure": {}},
        what_if={
            "improves_risk": True,
            "risk_delta": {"var_95_pct": 0.1},
            "constraints": {"passed": True, "violations": []},
        },
        recommended_action={"status": "observe"},
    )

    codes = [item["code"] for item in explanation["reason_codes"]]

    assert codes.count("scenario_loss_high") == 1
