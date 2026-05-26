from core.decision_ticket import build_decision_ticket


def test_build_decision_ticket_downgrades_when_data_quality_is_weak():
    from core.config import settings
    ticket = build_decision_ticket(
        data_quality={"score": 55, "status": "weak"},
        risk={"risk_level": "medium", "var_95_pct": -1.26},
        scenarios={"worst_scenario": {"portfolio_loss_pct": -6.75}},
    )

    var_high = getattr(settings, "CALIBRATED_VAR_HIGH", -6.0)
    assert ticket["decision_status"] == "limited"
    assert "data_quality_weak" in ticket["gates_failed"]
    assert ticket["policy_version"] == "institutional_policy_v1"
    assert len(ticket["policy_hash"]) == 64
    assert ticket["policy_hash"] == ticket["policy_snapshot"]["policy_hash"]
    assert ticket["policy_snapshot"]["thresholds"]["scenario_loss_limit_pct"] == var_high


def test_build_decision_ticket_includes_portfolio_exposure_summary():
    ticket = build_decision_ticket(
        data_quality={"score": 95, "status": "strong"},
        risk={"risk_level": "low", "var_95_pct": -0.9},
        scenarios={"worst_scenario": {"portfolio_loss_pct": -3.0}},
        portfolio={
            "asset_class_exposure": {"equity": 0.888889, "gold": 0.111111},
            "region_exposure": {"China": 0.444444, "US": 0.222222},
            "strategy_exposure": {"technology": 0.444444, "gold": 0.111111},
            "currency_exposure": {"CNY": 1.0},
            "largest_position": {"symbol": "CSI300_ETF", "weight": 0.111111},
            "top_3_weight": 0.333333,
            "concentration_level": "low",
        },
    )

    assert ticket["portfolio_summary"]["asset_class_exposure"]["equity"] == 0.888889
    assert ticket["portfolio_summary"]["region_exposure"]["China"] == 0.444444
    assert ticket["portfolio_summary"]["strategy_exposure"]["technology"] == 0.444444
    assert ticket["portfolio_summary"]["currency_exposure"]["CNY"] == 1.0
    assert ticket["portfolio_summary"]["concentration_level"] == "low"
