import os
import sqlite3
import time
import uuid

from app import config


class ClaimsRepository:
    """Persists claims and the claims_audit table. Nothing here is logged."""

    def __init__(self, db_path=None):
        self.db_path = db_path or config.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    beneficiary_id TEXT NOT NULL,
                    procedure_code TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    ai_decision TEXT,
                    ai_confidence REAL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )"""
            )
            cols = [r[1] for r in conn.execute("PRAGMA table_info(claims)").fetchall()]
            if "clinical_notes" not in cols:
                conn.execute("ALTER TABLE claims ADD COLUMN clinical_notes TEXT NOT NULL DEFAULT ''")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS claims_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    amount REAL,
                    outcome TEXT,
                    notes TEXT
                )"""
            )

    def create_claim(self, provider_id, beneficiary_id, procedure_code, amount, clinical_notes=""):
        claim_id = "CLM-" + uuid.uuid4().hex[:6].upper()
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO claims (claim_id, provider_id, beneficiary_id, procedure_code, amount, status, ai_decision, ai_confidence, created_at, updated_at, clinical_notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (claim_id, provider_id, beneficiary_id, procedure_code, amount, "SUBMITTED", None, None, now, now, clinical_notes or ""),
            )
        return self.get_claim(claim_id)

    def get_claim(self, claim_id):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        return dict(row) if row else None

    def list_claims(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM claims ORDER BY created_at DESC LIMIT 50").fetchall()
        return [dict(r) for r in rows]

    def update_status(self, claim_id, status, ai_decision=None, ai_confidence=None):
        with self._connect() as conn:
            if ai_decision is not None:
                conn.execute(
                    "UPDATE claims SET status=?, ai_decision=?, ai_confidence=?, updated_at=? WHERE claim_id=?",
                    (status, ai_decision, ai_confidence, time.time(), claim_id),
                )
            else:
                conn.execute(
                    "UPDATE claims SET status=?, updated_at=? WHERE claim_id=?",
                    (status, time.time(), claim_id),
                )
        return self.get_claim(claim_id)

    def write_audit(self, actor, action, claim_id, amount=None, outcome=None, notes=None):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO claims_audit (ts, actor, action, claim_id, amount, outcome, notes) VALUES (?,?,?,?,?,?,?)",
                (time.time(), actor, action, claim_id, amount, outcome, notes),
            )

    def list_audit(self, limit=100):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM claims_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
