from core.evidence_chain import build_evidence_chain


def test_evidence_chain_includes_metric_threshold_direction_and_source_quality():
    evidence = build_evidence_chain(
        decision_ticket={
            "score": 72,
            "decision_status": "limited",
            "policy_version": "institutional_policy_v1",
            "policy_hash": "a" * 64,
        },
        data_quality={"score": 78, "flags": ["fallback"], "source": "sample_portfolio"},
        risk={"var_95_pct": -1.25, "risk_level": "medium"},
        scenarios={"worst_scenario": {"id": "equity_liquidity_shock", "portfolio_loss_pct": -4.2}},
        factor_risk={"top_factor": {"factor_group": "macro", "factor_name": "equity_beta", "exposure": 0.88}},
        active_risk={"tracking_error_proxy_pct": 12.5, "largest_active_exposures": [{"symbol": "CSI300_ETF", "active_weight": 0.05}]},
        compliance={"status": "warn", "warnings": ["strategy_limit_near:technology"], "violations": []},
    )

    assert evidence["policy_version"] == "institutional_policy_v1"
    assert evidence["policy_hash"] == "a" * 64
    assert evidence["source_quality"]["mode"] == "fallback"
    assert evidence["items"][0]["metric"] == "data_quality_score"
    assert evidence["items"][0]["direction"] == "below_threshold"
    assert any(item["metric"] == "top_factor_exposure" for item in evidence["items"])
    assert any(item["metric"] == "compliance_status" and item["value"] == "warn" for item in evidence["items"])


def test_evidence_chain_marks_live_data_when_no_fallback_flags():
    evidence = build_evidence_chain(
        decision_ticket={"score": 90, "decision_status": "allow", "policy_version": "v", "policy_hash": "h"},
        data_quality={"score": 96, "flags": [], "source": "portfolio_file"},
        risk={"var_95_pct": -0.8, "risk_level": "low"},
        scenarios={"worst_scenario": {"id": "risk_on", "portfolio_loss_pct": -1.0}},
        factor_risk={"top_factor": {"factor_group": "region", "factor_name": "China", "exposure": 0.44}},
        active_risk={"tracking_error_proxy_pct": 4.0, "largest_active_exposures": []},
        compliance={"status": "pass", "warnings": [], "violations": []},
    )

    assert evidence["source_quality"]["mode"] == "live"
    assert evidence["items"][0]["direction"] == "above_threshold"
