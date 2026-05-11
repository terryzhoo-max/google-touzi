from core.audit_log import AuditLogStore


def test_audit_log_store_records_and_lists_decision_tickets(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))

    record = store.record_decision(
        payload={
            "decision_ticket": {"score": 83, "decision_status": "limited"},
            "recommended_action": {"status": "staged_execution"},
        },
        source="unit_test",
    )

    assert record["ticket_id"].startswith("dt_")
    assert record["source"] == "unit_test"
    assert record["score"] == 83
    assert record["decision_status"] == "limited"
    assert record["action_status"] == "staged_execution"
    assert len(record["payload_hash"]) == 64
    assert [item["window"] for item in record["review_schedule"]] == ["T+1", "T+5", "T+20"]

    rows = store.list_decisions(limit=5)
    assert len(rows) == 1
    assert rows[0]["ticket_id"] == record["ticket_id"]
    assert rows[0]["payload_hash"] == record["payload_hash"]


def test_audit_log_store_summarizes_policy_and_primary_driver(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))

    record = store.record_decision(
        payload={
            "policy": {"version": "institutional_policy_v1", "policy_hash": "a" * 64},
            "decision_ticket": {
                "score": 58,
                "decision_status": "observe",
                "policy_version": "institutional_policy_v1",
                "policy_hash": "a" * 64,
            },
            "decision_explanation": {
                "primary_driver": {"code": "scenario_loss_high"},
            },
            "recommended_action": {"status": "observe"},
        },
        source="unit_test",
    )

    rows = store.list_decisions(limit=5)
    loaded = store.get_decision(record["ticket_id"])

    assert record["policy_version"] == "institutional_policy_v1"
    assert record["policy_hash"] == "a" * 64
    assert record["primary_driver"] == "scenario_loss_high"
    assert rows[0]["policy_version"] == "institutional_policy_v1"
    assert rows[0]["policy_hash"] == "a" * 64
    assert rows[0]["primary_driver"] == "scenario_loss_high"
    assert loaded["policy_version"] == "institutional_policy_v1"
    assert loaded["policy_hash"] == "a" * 64
    assert loaded["primary_driver"] == "scenario_loss_high"


def test_audit_log_store_summarizes_benchmark_and_compliance(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))

    record = store.record_decision(
        payload={
            "policy": {"version": "institutional_policy_v1", "policy_hash": "a" * 64},
            "benchmark": {"benchmark_hash": "b" * 64},
            "compliance": {"status": "warn"},
            "decision_ticket": {
                "score": 82,
                "decision_status": "limited",
                "policy_version": "institutional_policy_v1",
                "policy_hash": "a" * 64,
            },
            "recommended_action": {"status": "staged_execution"},
        },
        source="unit_test",
    )

    rows = store.list_decisions(limit=5)
    loaded = store.get_decision(record["ticket_id"])

    assert record["benchmark_hash"] == "b" * 64
    assert record["compliance_status"] == "warn"
    assert rows[0]["benchmark_hash"] == "b" * 64
    assert rows[0]["compliance_status"] == "warn"
    assert loaded["benchmark_hash"] == "b" * 64
    assert loaded["compliance_status"] == "warn"


def test_audit_log_store_hydrates_payload_by_ticket_id(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))
    record = store.record_decision(
        payload={
            "decision_ticket": {"score": 71, "decision_status": "observe"},
            "recommended_action": {"status": "blocked"},
        },
        source="unit_test",
    )

    loaded = store.get_decision(record["ticket_id"])

    assert loaded["ticket_id"] == record["ticket_id"]
    assert loaded["review_schedule"][0]["ticket_id"] == record["ticket_id"]
    assert loaded["payload_hash"] == record["payload_hash"]
    assert loaded["payload"]["decision_ticket"]["score"] == 71
    assert loaded["payload"]["recommended_action"]["status"] == "blocked"


def test_audit_log_payload_hash_is_stable_for_canonical_payload(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))
    first = store.record_decision(
        payload={
            "recommended_action": {"status": "blocked"},
            "decision_ticket": {"decision_status": "observe", "score": 71},
        },
        source="unit_test",
    )
    second = store.record_decision(
        payload={
            "decision_ticket": {"score": 71, "decision_status": "observe"},
            "recommended_action": {"status": "blocked"},
        },
        source="unit_test",
    )

    assert first["payload_hash"] == second["payload_hash"]


def test_audit_log_store_verifies_payload_integrity(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))
    record = store.record_decision(
        payload={
            "decision_ticket": {"score": 71, "decision_status": "observe"},
            "recommended_action": {"status": "blocked"},
        },
        source="unit_test",
    )

    verification = store.verify_decision(record["ticket_id"])

    assert verification["ticket_id"] == record["ticket_id"]
    assert verification["verified"] is True
    assert verification["stored_hash"] == record["payload_hash"]
    assert verification["computed_hash"] == record["payload_hash"]


def test_audit_log_store_detects_tampered_payload(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))
    record = store.record_decision(
        payload={
            "decision_ticket": {"score": 71, "decision_status": "observe"},
            "recommended_action": {"status": "blocked"},
        },
        source="unit_test",
    )
    with store._connect() as conn:
        conn.execute(
            "UPDATE decision_audit_log SET payload_json = ? WHERE ticket_id = ?",
            ('{"decision_ticket":{"score":1}}', record["ticket_id"]),
        )
        conn.commit()

    verification = store.verify_decision(record["ticket_id"])

    assert verification["verified"] is False
    assert verification["stored_hash"] == record["payload_hash"]
    assert verification["computed_hash"] != record["payload_hash"]


def test_audit_log_store_detects_tampered_summary_columns(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))
    record = store.record_decision(
        payload={
            "policy": {"version": "institutional_policy_v1", "policy_hash": "a" * 64},
            "decision_ticket": {
                "score": 71,
                "decision_status": "observe",
                "policy_version": "institutional_policy_v1",
                "policy_hash": "a" * 64,
            },
            "decision_explanation": {
                "primary_driver": {"code": "scenario_loss_high"},
            },
            "recommended_action": {"status": "blocked"},
        },
        source="unit_test",
    )
    with store._connect() as conn:
        conn.execute(
            """
            UPDATE decision_audit_log
            SET policy_hash = ?, primary_driver = ?
            WHERE ticket_id = ?
            """,
            ("b" * 64, "risk_budget_medium", record["ticket_id"]),
        )
        conn.commit()

    verification = store.verify_decision(record["ticket_id"])

    assert verification["verified"] is False
    assert verification["payload_verified"] is True
    assert verification["summary_verified"] is False
    assert "policy_hash_mismatch" in verification["summary_errors"]
    assert "primary_driver_mismatch" in verification["summary_errors"]


def test_audit_log_store_detects_tampered_benchmark_and_compliance_summary(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))
    record = store.record_decision(
        payload={
            "policy": {"version": "institutional_policy_v1", "policy_hash": "a" * 64},
            "benchmark": {"benchmark_hash": "b" * 64},
            "compliance": {"status": "pass"},
            "decision_ticket": {
                "score": 88,
                "decision_status": "limited",
                "policy_version": "institutional_policy_v1",
                "policy_hash": "a" * 64,
            },
            "recommended_action": {"status": "staged_execution"},
        },
        source="unit_test",
    )
    with store._connect() as conn:
        conn.execute(
            """
            UPDATE decision_audit_log
            SET benchmark_hash = ?, compliance_status = ?
            WHERE ticket_id = ?
            """,
            ("c" * 64, "block", record["ticket_id"]),
        )
        conn.commit()

    verification = store.verify_decision(record["ticket_id"])

    assert verification["verified"] is False
    assert verification["payload_verified"] is True
    assert verification["summary_verified"] is False
    assert "benchmark_hash_mismatch" in verification["summary_errors"]
    assert "compliance_status_mismatch" in verification["summary_errors"]


def test_audit_log_store_verifies_recent_decision_batch(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))
    first = store.record_decision(
        payload={
            "decision_ticket": {"score": 71, "decision_status": "observe"},
            "recommended_action": {"status": "blocked"},
        },
        source="unit_test",
    )
    second = store.record_decision(
        payload={
            "decision_ticket": {"score": 88, "decision_status": "limited"},
            "recommended_action": {"status": "staged_execution"},
        },
        source="unit_test",
    )
    with store._connect() as conn:
        conn.execute(
            "UPDATE decision_audit_log SET payload_json = ? WHERE ticket_id = ?",
            ('{"decision_ticket":{"score":1}}', first["ticket_id"]),
        )
        conn.commit()

    batch = store.verify_recent_decisions(limit=10)

    assert batch["checked_count"] == 2
    assert batch["verified_count"] == 1
    assert batch["failed_count"] == 1
    assert batch["status"] == "failed"
    assert batch["verified_rate"] == 0.5
    assert batch["failed_ticket_ids"] == [first["ticket_id"]]
    assert [item["ticket_id"] for item in batch["results"]] == [second["ticket_id"], first["ticket_id"]]
    assert any(item["verified"] is False for item in batch["results"])


def test_audit_log_store_reports_passed_batch_when_all_records_verify(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))
    store.record_decision(
        payload={
            "decision_ticket": {"score": 88, "decision_status": "limited"},
            "recommended_action": {"status": "staged_execution"},
        },
        source="unit_test",
    )

    batch = store.verify_recent_decisions(limit=10)

    assert batch["status"] == "passed"
    assert batch["verified_rate"] == 1.0
    assert batch["failed_ticket_ids"] == []
    assert batch["checked_at"] > 0


def test_audit_log_store_reports_empty_batch_without_records(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))

    batch = store.verify_recent_decisions(limit=10)

    assert batch["status"] == "empty"
    assert batch["checked_count"] == 0
    assert batch["verified_rate"] == 0.0
    assert batch["failed_ticket_ids"] == []
    assert batch["checked_at"] > 0


def test_audit_log_store_persists_review_scores(tmp_path):
    store = AuditLogStore(str(tmp_path / "audit.db"))
    record = store.record_decision(
        payload={
            "decision_ticket": {"score": 78, "decision_status": "limited"},
            "recommended_action": {"status": "staged_execution"},
        },
        source="unit_test",
    )

    stored = store.record_review_score({
        "ticket_id": record["ticket_id"],
        "review_window": "T+1",
        "score": 90,
        "verdict": "effective",
        "evidence": ["action_executable", "risk_improved"],
    })

    assert stored["ticket_id"] == record["ticket_id"]
    assert stored["review_window"] == "T+1"
    assert stored["evidence"] == ["action_executable", "risk_improved"]

    listed = store.list_review_scores(ticket_id=record["ticket_id"])
    assert len(listed) == 1
    assert listed[0]["score"] == 90
    assert listed[0]["verdict"] == "effective"
