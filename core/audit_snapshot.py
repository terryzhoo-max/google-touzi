import json
import os
import hashlib
import sqlite3
import time

DEFAULT_AUDIT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "alphacore_audit.db")

class SnapshotAuditEngine:
    def __init__(self, db_path: str = DEFAULT_AUDIT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_snapshots (
                    ticket_id TEXT PRIMARY KEY,
                    snapshot_hash TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()

    def create_snapshot(self, ticket_id: str, payload: dict) -> str:
        """Create a canonical serialized JSON snapshot and compute its cryptographic SHA-256 hash."""
        # Canonical representation to keep deterministic hash
        payload_str = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        snap_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decision_snapshots (ticket_id, snapshot_hash, snapshot_json, created_at)
                VALUES (?, ?, ?, ?)
            """, (ticket_id, snap_hash, payload_str, time.time()))
            conn.commit()
        return snap_hash

    def verify_snapshot(self, ticket_id: str) -> dict:
        """Verify the integrity of a stored snapshot against its recorded SHA-256 hash."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT snapshot_hash, snapshot_json, created_at FROM decision_snapshots WHERE ticket_id = ?",
                (ticket_id,)
            ).fetchone()
            
        if not row:
            return {
                "ticket_id": ticket_id,
                "verified": False,
                "status": "NOT_FOUND",
                "error": "Snapshot not found in database."
            }
            
        stored_hash, snapshot_json, created_at = row
        try:
            payload = json.loads(snapshot_json)
            computed_hash = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
            verified = (stored_hash == computed_hash)
            return {
                "ticket_id": ticket_id,
                "verified": verified,
                "status": "SUCCESS" if verified else "TAMPERED",
                "stored_hash": stored_hash,
                "computed_hash": computed_hash,
                "created_at": created_at,
                "payload": payload
            }
        except Exception as e:
            return {
                "ticket_id": ticket_id,
                "verified": False,
                "status": "CORRUPTED",
                "error": f"Failed to parse snapshot JSON: {e}"
            }
