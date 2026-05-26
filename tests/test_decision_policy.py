from core.decision_policy import DecisionPolicy, get_default_decision_policy
from core.decision_ticket import build_decision_ticket


def test_default_decision_policy_has_auditable_version_and_thresholds():
    policy = get_default_decision_policy()

    assert policy["version"] == "institutional_policy_v1"
    assert len(policy["policy_hash"]) == 64
    assert policy["thresholds"]["data_quality_min_score"] == 60
    assert policy["thresholds"]["scenario_loss_limit_pct"] == -8.0
    assert policy["thresholds"]["scenario_loss_watch_pct"] == -6.0
    assert policy["thresholds"]["allow_min_score"] == 70
    assert policy["thresholds"]["limited_min_score"] == 50


def test_decision_policy_hash_changes_when_thresholds_change():
    first = DecisionPolicy().to_dict()
    second = DecisionPolicy(scenario_loss_limit_pct=-10.0).to_dict()

    assert first["policy_hash"] != second["policy_hash"]


def test_decision_ticket_uses_policy_thresholds_and_records_snapshot():
    policy = DecisionPolicy(
        version="test_policy_v2",
        data_quality_min_score=70,
        scenario_loss_limit_pct=-10.0,
        scenario_loss_watch_pct=-5.0,
        allow_min_score=85,
        limited_min_score=75,
    )

    ticket = build_decision_ticket(
        data_quality={"score": 65, "status": "usable"},
        risk={"risk_level": "low", "var_95_pct": -0.9},
        scenarios={"worst_scenario": {"portfolio_loss_pct": -5.5}},
        policy=policy,
    )

    assert ticket["policy_version"] == "test_policy_v2"
    assert ticket["policy_hash"] == policy.to_dict()["policy_hash"]
    assert ticket["policy_snapshot"]["thresholds"]["data_quality_min_score"] == 70
    assert ticket["decision_status"] == "observe"
    assert "data_quality_weak" in ticket["gates_failed"]
