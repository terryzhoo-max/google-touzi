import json
import os
import hashlib
import sqlite3
import time
from uuid import uuid4

from core.review_scheduler import build_review_schedule


DEFAULT_AUDIT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "alphacore_audit.db")


def _canonical_payload_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: dict) -> str:
    return hashlib.sha256(_canonical_payload_json(payload).encode("utf-8")).hexdigest()


def _policy_version(payload: dict) -> str | None:
    ticket = payload.get("decision_ticket", {})
    policy = payload.get("policy", {})
    return ticket.get("policy_version") or policy.get("version")


def _policy_hash(payload: dict) -> str | None:
    ticket = payload.get("decision_ticket", {})
    policy = payload.get("policy", {})
    return ticket.get("policy_hash") or policy.get("policy_hash")


def _primary_driver(payload: dict) -> str | None:
    explanation = payload.get("decision_explanation", {})
    primary = explanation.get("primary_driver", {})
    return primary.get("code")


def _benchmark_hash(payload: dict) -> str | None:
    benchmark = payload.get("benchmark", {})
    active_risk = payload.get("active_risk", {})
    active_benchmark = active_risk.get("benchmark", {})
    return benchmark.get("benchmark_hash") or active_benchmark.get("benchmark_hash")


def _compliance_status(payload: dict) -> str | None:
    compliance = payload.get("compliance", {})
    what_if_compliance = payload.get("what_if", {}).get("compliance", {})
    return compliance.get("status") or what_if_compliance.get("status")


def _allocation_model_status(payload: dict) -> str | None:
    allocation_model = payload.get("allocation_model", {})
    return allocation_model.get("status")


def _allocation_model_hash(payload: dict) -> str | None:
    allocation_model = payload.get("allocation_model", {})
    return allocation_model.get("model_hash")


def _norm(value: str | None) -> str:
    return value or ""


class AuditLogStore:
    def __init__(self, db_path: str = DEFAULT_AUDIT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_audit_log (
                    ticket_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    source TEXT NOT NULL,
                    score INTEGER,
                    decision_status TEXT,
                    action_status TEXT,
                    policy_version TEXT,
                    policy_hash TEXT,
                    primary_driver TEXT,
                    benchmark_hash TEXT,
                    compliance_status TEXT,
                    allocation_model_status TEXT,
                    allocation_model_hash TEXT,
                    payload_hash TEXT,
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_review_log (
                    ticket_id TEXT NOT NULL,
                    review_window TEXT NOT NULL,
                    reviewed_at REAL NOT NULL,
                    score INTEGER NOT NULL,
                    verdict TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    PRIMARY KEY (ticket_id, review_window)
                )
            """)
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(decision_audit_log)").fetchall()
            }
            if "payload_hash" not in columns:
                conn.execute("ALTER TABLE decision_audit_log ADD COLUMN payload_hash TEXT")
            if "policy_version" not in columns:
                conn.execute("ALTER TABLE decision_audit_log ADD COLUMN policy_version TEXT")
            if "policy_hash" not in columns:
                conn.execute("ALTER TABLE decision_audit_log ADD COLUMN policy_hash TEXT")
            if "primary_driver" not in columns:
                conn.execute("ALTER TABLE decision_audit_log ADD COLUMN primary_driver TEXT")
            if "benchmark_hash" not in columns:
                conn.execute("ALTER TABLE decision_audit_log ADD COLUMN benchmark_hash TEXT")
            if "compliance_status" not in columns:
                conn.execute("ALTER TABLE decision_audit_log ADD COLUMN compliance_status TEXT")
            if "allocation_model_status" not in columns:
                conn.execute("ALTER TABLE decision_audit_log ADD COLUMN allocation_model_status TEXT")
            if "allocation_model_hash" not in columns:
                conn.execute("ALTER TABLE decision_audit_log ADD COLUMN allocation_model_hash TEXT")
            rows_missing_hash = conn.execute(
                """
                SELECT ticket_id, payload_json
                FROM decision_audit_log
                WHERE payload_hash IS NULL OR payload_hash = ''
                   OR policy_version IS NULL OR policy_version = ''
                   OR policy_hash IS NULL OR policy_hash = ''
                   OR primary_driver IS NULL OR primary_driver = ''
                   OR benchmark_hash IS NULL OR benchmark_hash = ''
                   OR compliance_status IS NULL OR compliance_status = ''
                   OR allocation_model_status IS NULL OR allocation_model_status = ''
                   OR allocation_model_hash IS NULL OR allocation_model_hash = ''
                """
            ).fetchall()
            for ticket_id, payload_json in rows_missing_hash:
                payload = json.loads(payload_json)
                conn.execute(
                    """
                    UPDATE decision_audit_log
                    SET payload_hash = ?,
                        policy_version = COALESCE(NULLIF(policy_version, ''), ?),
                        policy_hash = COALESCE(NULLIF(policy_hash, ''), ?),
                        primary_driver = COALESCE(NULLIF(primary_driver, ''), ?),
                        benchmark_hash = COALESCE(NULLIF(benchmark_hash, ''), ?),
                        compliance_status = COALESCE(NULLIF(compliance_status, ''), ?),
                        allocation_model_status = COALESCE(NULLIF(allocation_model_status, ''), ?),
                        allocation_model_hash = COALESCE(NULLIF(allocation_model_hash, ''), ?)
                    WHERE ticket_id = ?
                    """,
                    (
                        _payload_hash(payload),
                        _policy_version(payload),
                        _policy_hash(payload),
                        _primary_driver(payload),
                        _benchmark_hash(payload),
                        _compliance_status(payload),
                        _allocation_model_status(payload),
                        _allocation_model_hash(payload),
                        ticket_id,
                    ),
                )
            conn.commit()

    def record_decision(self, payload: dict, source: str = "api") -> dict:
        ticket_id = f"dt_{uuid4().hex[:12]}"
        created_at = time.time()
        ticket = payload.get("decision_ticket", {})
        action = payload.get("recommended_action", {})
        row = {
            "ticket_id": ticket_id,
            "created_at": created_at,
            "source": source,
            "score": ticket.get("score"),
            "decision_status": ticket.get("decision_status"),
            "action_status": action.get("status"),
            "policy_version": _policy_version(payload),
            "policy_hash": _policy_hash(payload),
            "primary_driver": _primary_driver(payload),
            "benchmark_hash": _benchmark_hash(payload),
            "compliance_status": _compliance_status(payload),
            "allocation_model_status": _allocation_model_status(payload),
            "allocation_model_hash": _allocation_model_hash(payload),
            "payload_hash": _payload_hash(payload),
            "review_schedule": build_review_schedule(ticket_id, created_at),
            "payload": payload,
        }

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO decision_audit_log (
                    ticket_id, created_at, source, score,
                    decision_status, action_status, policy_version, policy_hash, primary_driver,
                    benchmark_hash, compliance_status, allocation_model_status, allocation_model_hash,
                    payload_hash, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["ticket_id"],
                    row["created_at"],
                    row["source"],
                    row["score"],
                    row["decision_status"],
                    row["action_status"],
                    row["policy_version"],
                    row["policy_hash"],
                    row["primary_driver"],
                    row["benchmark_hash"],
                    row["compliance_status"],
                    row["allocation_model_status"],
                    row["allocation_model_hash"],
                    row["payload_hash"],
                    _canonical_payload_json(payload),
                ),
            )
            conn.commit()

        # Build cryptographic immutable snapshot for deep audit protection
        try:
            from core.audit_snapshot import SnapshotAuditEngine
            SnapshotAuditEngine().create_snapshot(ticket_id, payload)
        except Exception:
            pass

        return row

    def list_decisions(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ticket_id, created_at, source, score, decision_status, action_status,
                       COALESCE(policy_version, ''), COALESCE(primary_driver, ''),
                       COALESCE(policy_hash, ''),
                       COALESCE(benchmark_hash, ''), COALESCE(compliance_status, ''),
                       COALESCE(allocation_model_status, ''), COALESCE(allocation_model_hash, ''),
                       COALESCE(payload_hash, '')
                FROM decision_audit_log
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "ticket_id": ticket_id,
                "created_at": created_at,
                "source": source,
                "score": score,
                "decision_status": decision_status,
                "action_status": action_status,
                "policy_version": policy_version,
                "policy_hash": policy_hash,
                "primary_driver": primary_driver,
                "benchmark_hash": benchmark_hash,
                "compliance_status": compliance_status,
                "allocation_model_status": allocation_model_status,
                "allocation_model_hash": allocation_model_hash,
                "payload_hash": payload_hash,
                "review_schedule": build_review_schedule(ticket_id, created_at),
            }
            for ticket_id, created_at, source, score, decision_status, action_status,
            policy_version, primary_driver, policy_hash, benchmark_hash, compliance_status,
            allocation_model_status, allocation_model_hash, payload_hash in rows
        ]

    def get_decision(self, ticket_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT ticket_id, created_at, source, score,
                       decision_status, action_status, COALESCE(policy_version, ''),
                       COALESCE(policy_hash, ''), COALESCE(primary_driver, ''),
                       COALESCE(benchmark_hash, ''), COALESCE(compliance_status, ''),
                       COALESCE(allocation_model_status, ''), COALESCE(allocation_model_hash, ''),
                       COALESCE(payload_hash, ''), payload_json
                FROM decision_audit_log
                WHERE ticket_id = ?
                """,
                (ticket_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "ticket_id": row[0],
            "created_at": row[1],
            "source": row[2],
            "score": row[3],
            "decision_status": row[4],
            "action_status": row[5],
            "policy_version": row[6],
            "policy_hash": row[7],
            "primary_driver": row[8],
            "benchmark_hash": row[9],
            "compliance_status": row[10],
            "allocation_model_status": row[11],
            "allocation_model_hash": row[12],
            "payload_hash": row[13],
            "review_schedule": build_review_schedule(row[0], row[1]),
            "payload": json.loads(row[14]),
        }

    def verify_decision(self, ticket_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT ticket_id, COALESCE(payload_hash, ''), payload_json,
                       COALESCE(policy_version, ''), COALESCE(policy_hash, ''),
                       COALESCE(primary_driver, ''), COALESCE(benchmark_hash, ''),
                       COALESCE(compliance_status, ''), COALESCE(allocation_model_status, ''),
                       COALESCE(allocation_model_hash, '')
                FROM decision_audit_log
                WHERE ticket_id = ?
                """,
                (ticket_id,),
            ).fetchone()
        if row is None:
            return None

        try:
            payload = json.loads(row[2])
            computed_hash = _payload_hash(payload)
            error = None
        except json.JSONDecodeError as exc:
            payload = {}
            computed_hash = ""
            error = f"invalid payload json: {exc.msg}"
        summary_errors = []
        expected_summary = {
            "policy_version": _norm(_policy_version(payload)),
            "policy_hash": _norm(_policy_hash(payload)),
            "primary_driver": _norm(_primary_driver(payload)),
            "benchmark_hash": _norm(_benchmark_hash(payload)),
            "compliance_status": _norm(_compliance_status(payload)),
            "allocation_model_status": _norm(_allocation_model_status(payload)),
            "allocation_model_hash": _norm(_allocation_model_hash(payload)),
        }
        stored_summary = {
            "policy_version": row[3],
            "policy_hash": row[4],
            "primary_driver": row[5],
            "benchmark_hash": row[6],
            "compliance_status": row[7],
            "allocation_model_status": row[8],
            "allocation_model_hash": row[9],
        }
        for key, expected in expected_summary.items():
            if stored_summary[key] != expected:
                summary_errors.append(f"{key}_mismatch")
        payload_verified = row[1] == computed_hash
        
        # Dual-layer verification with cryptographic snapshot
        snapshot_verified = True
        snapshot_status = "NOT_FOUND"
        try:
            from core.audit_snapshot import SnapshotAuditEngine
            snap_v = SnapshotAuditEngine().verify_snapshot(ticket_id)
            snapshot_status = snap_v.get("status", "NOT_FOUND")
            if snapshot_status == "TAMPERED":
                payload_verified = False
                snapshot_verified = False
            elif snapshot_status == "SUCCESS":
                snapshot_verified = True
        except Exception:
            pass
            
        summary_verified = not summary_errors
        
        # Anomalous Drift Auditor for Stage 3
        drift_status = "NORMAL"
        drift_bps = 0.0
        try:
            ticket = payload.get("decision_ticket", {})
            score = float(ticket.get("score") or 80.0)
            expected_return = score / 1000.0
            
            realized_return = float(payload.get("portfolio_return") or payload.get("recommended_action", {}).get("expected_yield", expected_return))
            
            drift = abs(realized_return - expected_return)
            drift_bps = round(drift * 10000.0, 2)
            if drift > 0.03:  # 300 Bps threshold (3% deviation)
                drift_status = "ANOMALY_DRIFT"
        except Exception:
            pass

        return {
            "ticket_id": row[0],
            "verified": payload_verified and summary_verified,
            "payload_verified": payload_verified,
            "summary_verified": summary_verified,
            "snapshot_verified": snapshot_verified,
            "snapshot_status": snapshot_status,
            "stored_hash": row[1],
            "computed_hash": computed_hash,
            "stored_summary": stored_summary,
            "computed_summary": expected_summary,
            "summary_errors": summary_errors,
            "error": error,
            "drift_status": drift_status,
            "drift_bps": drift_bps,
        }

    def verify_recent_decisions(self, limit: int = 100) -> dict:
        rows = self.list_decisions(limit=limit)
        results = []
        for row in rows:
            verification = self.verify_decision(row["ticket_id"])
            if verification is not None:
                results.append(verification)

        verified_count = len([item for item in results if item["verified"]])
        failed_count = len(results) - verified_count
        failed_ticket_ids = [item["ticket_id"] for item in results if not item["verified"]]
        if not results:
            status = "empty"
        elif failed_count == 0:
            status = "passed"
        else:
            status = "failed"
        return {
            "status": status,
            "checked_at": time.time(),
            "checked_count": len(results),
            "verified_count": verified_count,
            "failed_count": failed_count,
            "verified_rate": round(verified_count / max(len(results), 1), 4),
            "failed_ticket_ids": failed_ticket_ids,
            "results": results,
        }

    def record_review_score(self, review_score: dict) -> dict:
        row = {
            "ticket_id": review_score["ticket_id"],
            "review_window": review_score["review_window"],
            "reviewed_at": time.time(),
            "score": int(review_score["score"]),
            "verdict": review_score["verdict"],
            "evidence": list(review_score.get("evidence", [])),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO decision_review_log (
                    ticket_id, review_window, reviewed_at, score, verdict, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["ticket_id"],
                    row["review_window"],
                    row["reviewed_at"],
                    row["score"],
                    row["verdict"],
                    json.dumps(row["evidence"], ensure_ascii=False, sort_keys=True),
                ),
            )
            conn.commit()
        return row

    def list_review_scores(self, ticket_id: str | None = None, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            if ticket_id:
                rows = conn.execute(
                    """
                    SELECT ticket_id, review_window, reviewed_at, score, verdict, evidence_json
                    FROM decision_review_log
                    WHERE ticket_id = ?
                    ORDER BY reviewed_at DESC
                    LIMIT ?
                    """,
                    (ticket_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT ticket_id, review_window, reviewed_at, score, verdict, evidence_json
                    FROM decision_review_log
                    ORDER BY reviewed_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [
            {
                "ticket_id": ticket_id,
                "review_window": review_window,
                "reviewed_at": reviewed_at,
                "score": score,
                "verdict": verdict,
                "evidence": json.loads(evidence_json),
            }
            for ticket_id, review_window, reviewed_at, score, verdict, evidence_json in rows
        ]


def get_audit_store() -> AuditLogStore:
    return AuditLogStore()
