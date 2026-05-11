from fastapi.testclient import TestClient

from data_engine import _build_institutional_data_quality, app
from core.config import settings


client = TestClient(app)


def test_health_endpoint_includes_production_diagnostics_without_secrets(monkeypatch):
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "secret-value-should-not-leak", raising=False)

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert "diagnostics" in payload
    diagnostics = payload["diagnostics"]
    assert diagnostics["status"] in {"healthy", "degraded", "misconfigured"}
    assert "config" in diagnostics
    assert "portfolio" in diagnostics
    assert "audit_db" in diagnostics
    assert "git" in diagnostics
    assert diagnostics["optional_keys"]["DEEPSEEK_API_KEY"] == "present"
    assert "secret-value-should-not-leak" not in str(payload)


def test_institutional_decision_endpoint_returns_ticket():
    response = client.get("/api/institutional/decision")

    assert response.status_code == 200
    payload = response.json()
    assert payload["portfolio"]["total_market_value"] == 900000.0
    assert "risk" in payload
    assert "scenarios" in payload
    assert payload["decision_ticket"]["review_schedule"] == ["T+1", "T+5", "T+20"]
    assert payload["policy"]["version"] == "institutional_policy_v1"
    assert len(payload["policy"]["policy_hash"]) == 64
    assert payload["decision_ticket"]["policy_version"] == payload["policy"]["version"]
    assert payload["decision_ticket"]["policy_hash"] == payload["policy"]["policy_hash"]
    assert payload["decision_explanation"]["policy_version"] == payload["policy"]["version"]
    assert payload["decision_explanation"]["policy_hash"] == payload["policy"]["policy_hash"]
    assert "recommended_action" in payload
    assert "factor_risk" in payload
    assert "benchmark" in payload
    assert "active_risk" in payload
    assert "compliance" in payload
    assert "evidence_chain" in payload
    assert payload["compliance"]["status"] in {"pass", "warn", "block"}
    assert payload["benchmark"]["version"] == "benchmark_v1"
    assert len(payload["benchmark"]["benchmark_hash"]) == 64
    assert payload["evidence_chain"]["policy_hash"] == payload["policy"]["policy_hash"]
    assert payload["decision_explanation"]["execution_readiness"] in {
        "executable",
        "executable_with_review",
        "review_required",
        "blocked",
    }
    assert "primary_driver" in payload["decision_explanation"]
    assert "reason_codes" in payload["decision_explanation"]
    assert payload["audit"]["record_endpoint"] == "/api/institutional/audit/decisions"


def test_institutional_component_endpoints_return_stable_contracts():
    portfolio = client.get("/api/institutional/portfolio").json()
    quality = client.get("/api/institutional/data_quality").json()
    risk = client.get("/api/institutional/risk").json()
    scenarios = client.get("/api/institutional/scenarios").json()
    policy = client.get("/api/institutional/policy").json()
    factors = client.get("/api/institutional/factors").json()
    benchmark = client.get("/api/institutional/benchmark").json()
    active_risk = client.get("/api/institutional/active_risk").json()
    attribution = client.get("/api/institutional/attribution").json()
    compliance = client.get("/api/institutional/compliance").json()

    assert portfolio["position_count"] == 9
    assert portfolio["positions"][0]["symbol"] == "CSI300_ETF"
    assert portfolio["region_exposure"]["China"] == 0.444444
    assert portfolio["region_exposure"]["US"] == 0.222222
    assert portfolio["region_exposure"]["Japan"] == 0.111111
    assert portfolio["region_exposure"]["Gold"] == 0.111111
    assert quality["status"] == "strong"
    assert quality["source"] == "portfolio_file"
    assert "var_95_pct" in risk
    assert scenarios["worst_scenario"]["id"] == "equity_liquidity_shock"
    assert policy["version"] == "institutional_policy_v1"
    assert len(policy["policy_hash"]) == 64
    assert "thresholds" in policy
    assert factors["coverage"]["mapped_positions"] == 9
    assert "factor_groups" in factors
    assert benchmark["benchmark_id"] == "alphacore_policy_benchmark"
    assert active_risk["benchmark"]["benchmark_hash"] == benchmark["benchmark_hash"]
    assert "tracking_error_proxy_pct" in active_risk
    assert attribution["period"] == "T+1"
    assert "decision_effect" in attribution
    assert compliance["status"] in {"pass", "warn", "block"}
    assert "policy_hash" in compliance


def test_institutional_compliance_check_accepts_adjustments():
    response = client.post(
        "/api/institutional/compliance/check",
        json={"adjustments": {"CSI300_ETF": -0.05, "GOLD_ETF": 0.05}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"pass", "warn", "block"}
    assert "violations" in payload


def test_institutional_attribution_endpoint_respects_period_parameter():
    t1 = client.get("/api/institutional/attribution?period=T%2B1").json()
    t5 = client.get("/api/institutional/attribution?period=T%2B5").json()

    assert t1["period"] == "T+1"
    assert t5["period"] == "T+5"


def test_institutional_data_quality_marks_missing_portfolio_file_as_fallback(monkeypatch, tmp_path):
    missing_path = tmp_path / "missing_portfolio.json"
    monkeypatch.setattr(settings, "PORTFOLIO_BOOK_PATH", str(missing_path))

    quality = _build_institutional_data_quality()

    assert quality["source"] == "sample_portfolio"
    assert "fallback" in quality["flags"]
    assert quality["status"] == "strong"


def test_institutional_what_if_endpoint_returns_risk_delta():
    response = client.get("/api/institutional/what_if")

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_weights"]["CSI300_ETF"] < payload["before"]["portfolio"]["positions"][0]["weight"]
    assert payload["target_weights"]["GOLD_ETF"] > payload["before"]["portfolio"]["positions"][-1]["weight"]
    assert payload["constraints"]["passed"] is True
    assert payload["improves_risk"] is True


def test_institutional_action_endpoint_returns_executable_action():
    response = client.get("/api/institutional/action")

    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "action" in payload
    assert "risk_improvement" in payload


def test_institutional_audit_endpoints_record_and_list_decision():
    response = client.post("/api/institutional/audit/decisions")

    assert response.status_code == 200
    payload = response.json()
    ticket_id = payload["record"]["ticket_id"]
    assert ticket_id.startswith("dt_")
    assert len(payload["record"]["payload_hash"]) == 64
    assert payload["record"]["policy_version"] == "institutional_policy_v1"
    assert payload["record"]["policy_hash"] == payload["payload"]["policy"]["policy_hash"]
    assert payload["record"]["primary_driver"]

    listed = client.get("/api/institutional/audit/decisions").json()
    assert any(row["ticket_id"] == ticket_id for row in listed["decisions"])
    listed_row = next(row for row in listed["decisions"] if row["ticket_id"] == ticket_id)
    assert listed_row["policy_version"] == payload["record"]["policy_version"]
    assert listed_row["policy_hash"] == payload["record"]["policy_hash"]
    assert listed_row["primary_driver"] == payload["record"]["primary_driver"]

    loaded = client.get(f"/api/institutional/audit/decisions/{ticket_id}").json()
    assert loaded["ticket_id"] == ticket_id
    assert loaded["payload_hash"] == payload["record"]["payload_hash"]
    assert loaded["policy_version"] == payload["record"]["policy_version"]
    assert loaded["policy_hash"] == payload["record"]["policy_hash"]
    assert loaded["primary_driver"] == payload["record"]["primary_driver"]
    assert loaded["review_schedule"][0]["window"] == "T+1"
    assert "decision_ticket" in loaded["payload"]

    verification = client.get(f"/api/institutional/audit/decisions/{ticket_id}/verify")
    assert verification.status_code == 200
    assert verification.json()["verified"] is True

    batch_verification = client.get("/api/institutional/audit/verify?limit=10")
    assert batch_verification.status_code == 200
    assert "checked_count" in batch_verification.json()
    assert "failed_count" in batch_verification.json()
    assert "status" in batch_verification.json()
    assert "verified_rate" in batch_verification.json()
    assert "failed_ticket_ids" in batch_verification.json()
    assert "checked_at" in batch_verification.json()


def test_institutional_due_reviews_endpoint_returns_review_queue():
    response = client.get("/api/institutional/reviews/due")

    assert response.status_code == 200
    payload = response.json()
    assert "reviews" in payload


def test_institutional_review_summary_endpoint_returns_scheduler_counts():
    response = client.get("/api/institutional/reviews/summary")

    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "due_count" in payload["summary"]
    assert "critical_due_count" in payload["summary"]
    assert "elevated_due_count" in payload["summary"]


def test_institutional_review_queue_endpoint_returns_prioritized_queue():
    response = client.get("/api/institutional/reviews/queue")

    assert response.status_code == 200
    payload = response.json()
    assert "queue" in payload
    assert "returned_count" in payload
    assert payload["filters"]["limit"] == 50

    filtered = client.get("/api/institutional/reviews/queue?priority=critical&limit=1")
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert "queue" in filtered_payload
    assert filtered_payload["filters"] == {"priority": "critical", "limit": 1}

    invalid = client.get("/api/institutional/reviews/queue?priority=urgent")
    assert invalid.status_code == 400


def test_institutional_review_score_endpoint_scores_recorded_decision():
    created = client.post("/api/institutional/audit/decisions").json()
    ticket_id = created["record"]["ticket_id"]

    response = client.get(f"/api/institutional/reviews/{ticket_id}/score?window=T%2B1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticket_id"] == ticket_id
    assert payload["review_window"] == "T+1"
    assert "verdict" in payload

    persisted = client.post(f"/api/institutional/reviews/{ticket_id}/score?window=T%2B1")
    assert persisted.status_code == 200
    assert persisted.json()["recorded"] is True

    listed = client.get(f"/api/institutional/reviews/scores?ticket_id={ticket_id}")
    assert listed.status_code == 200
    assert any(item["ticket_id"] == ticket_id for item in listed.json()["scores"])


def test_institutional_due_review_scores_endpoint_returns_scores():
    response = client.get("/api/institutional/reviews/scores/due")

    assert response.status_code == 200
    assert "scores" in response.json()

    persisted = client.post("/api/institutional/reviews/scores/due")
    assert persisted.status_code == 200
    assert "recorded_count" in persisted.json()
