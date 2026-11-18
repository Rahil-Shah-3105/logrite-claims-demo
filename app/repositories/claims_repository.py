import os
import sqlite3
import time
import uuid

from app import config
import logging
logger = logging.getLogger(__name__)


class ClaimsRepository:
    """Persists claims and the claims_audit table. Nothing here is logged."""

    def __init__(self, db_path=None):
        logger.debug(">>> Entering __init__(db_path=%s)", db_path, extra={"event.action": "__init__", "logrite.db_path": db_path})
        self.db_path = db_path or config.DB_PATH
        logger.debug("__init__(self=%s,db_path=%s): self.db_path → %s", self, db_path, self.db_path, extra={"event.action": "__init__", "logrite.db_path": db_path})
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()
        logger.debug("<<< Exiting __init__(db_path=%s)", db_path, extra={"event.action": "__init__", "logrite.db_path": db_path})

    def _connect(self):
        logger.debug(">>> Entering _connect()", extra={"event.action": "_connect"})
        conn = sqlite3.connect(self.db_path)
        logger.debug("_connect(): conn → %s", conn, extra={"event.action": "_connect"})
        conn.row_factory = sqlite3.Row
        logger.debug("_connect(self=%s): conn.row_factory → %s", self, conn.row_factory, extra={"event.action": "_connect"})
        logger.debug("<<< Exiting _connect()", extra={"event.action": "_connect"})
        return conn

    def _init_schema(self):
        logger.debug(">>> Entering _init_schema()", extra={"event.action": "_init_schema"})
        __log_start = time.time()
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
            logger.info("_init_schema()=: query operation took %s ms", int((time.time() - __log_start) * 1000), extra={"event.action": "_init_schema", "event.category": "database"})
            cols = [r[1] for r in conn.execute("PRAGMA table_info(claims)").fetchall()]
            logger.debug("_init_schema(): cols → %s", cols, extra={"event.action": "_init_schema"})
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
            logger.debug("<<< Exiting _init_schema()", extra={"event.action": "_init_schema"})

    def create_claim(self, provider_id, beneficiary_id, procedure_code, amount, clinical_notes=""):
        logger.debug(">>> Entering create_claim(provider_id=<redacted>,beneficiary_id=<redacted>,procedure_code=%s,amount=%s,clinical_notes=<redacted>)", procedure_code, amount, extra={"event.action": "create_claim", "logrite.procedure_code": procedure_code, "logrite.amount": amount})
        __log_start = time.time()
        claim_id = "CLM-" + uuid.uuid4().hex[:6].upper()
        logger.debug("create_claim(provider_id=<redacted>,beneficiary_id=<redacted>,procedure_code=%s,amount=%s,clinical_notes=<redacted>): claim_id → %s", procedure_code, amount, claim_id, extra={"event.action": "create_claim", "logrite.procedure_code": procedure_code, "logrite.amount": amount})
        now = time.time()
        with self._connect() as conn:
            logger.debug("create_claim(provider_id=<redacted>,beneficiary_id=<redacted>,procedure_code=%s,amount=%s,clinical_notes=<redacted>): now → %s", procedure_code, amount, now, extra={"event.action": "create_claim", "logrite.procedure_code": procedure_code, "logrite.amount": amount})
            conn.execute(
                "INSERT INTO claims (claim_id, provider_id, beneficiary_id, procedure_code, amount, status, ai_decision, ai_confidence, created_at, updated_at, clinical_notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (claim_id, provider_id, beneficiary_id, procedure_code, amount, "SUBMITTED", None, None, now, now, clinical_notes or ""),
            )
        logger.info("create_claim(provider_id,beneficiary_id,procedure_code,amount,clinical_notes)=<redacted>,<redacted>,%s,%s,<redacted>: save operation took %s ms", procedure_code, amount, int((time.time() - __log_start) * 1000), extra={"event.action": "create_claim", "event.category": "database", "logrite.procedure_code": procedure_code, "logrite.amount": amount})
        logger.debug("<<< Exiting create_claim(provider_id=<redacted>,beneficiary_id=<redacted>,procedure_code=%s,amount=%s,clinical_notes=<redacted>)", procedure_code, amount, extra={"event.action": "create_claim", "logrite.procedure_code": procedure_code, "logrite.amount": amount})
        return self.get_claim(claim_id)

    def get_claim(self, claim_id):
        logger.debug(">>> Entering get_claim(claim_id=%s)", claim_id, extra={"event.action": "get_claim", "logrite.claim_id": claim_id})
        __log_start = time.time()
        with self._connect() as conn:
            logger.debug("<<< Exiting get_claim(claim_id=%s)", claim_id, extra={"event.action": "get_claim", "logrite.claim_id": claim_id})
            logger.info("get_claim(claim_id)=%s: find operation took %s ms", claim_id, int((time.time() - __log_start) * 1000), extra={"event.action": "get_claim", "event.category": "database", "logrite.claim_id": claim_id})
            row = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        logger.debug("get_claim(claim_id=%s): row → %s", claim_id, row, extra={"event.action": "get_claim", "logrite.claim_id": claim_id})
        return dict(row) if row else None

    def list_claims(self):
        logger.debug(">>> Entering list_claims()", extra={"event.action": "list_claims"})
        __log_start = time.time()
        with self._connect() as conn:
            logger.debug("<<< Exiting list_claims()", extra={"event.action": "list_claims"})
            logger.info("list_claims()=: find operation took %s ms", int((time.time() - __log_start) * 1000), extra={"event.action": "list_claims", "event.category": "database"})
            rows = conn.execute("SELECT * FROM claims ORDER BY created_at DESC LIMIT 50").fetchall()
        logger.debug("list_claims(): rows → %s", rows, extra={"event.action": "list_claims"})
        return [dict(r) for r in rows]

    def update_status(self, claim_id, status, ai_decision=None, ai_confidence=None):
        logger.debug(">>> Entering update_status(claim_id=%s,status=%s,ai_decision=%s,ai_confidence=%s)", claim_id, status, ai_decision, ai_confidence, extra={"event.action": "update_status", "logrite.claim_id": claim_id, "logrite.status": status, "logrite.ai_decision": ai_decision, "logrite.ai_confidence": ai_confidence})
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
        logger.debug("<<< Exiting update_status(claim_id=%s,status=%s,ai_decision=%s,ai_confidence=%s)", claim_id, status, ai_decision, ai_confidence, extra={"event.action": "update_status", "logrite.claim_id": claim_id, "logrite.status": status, "logrite.ai_decision": ai_decision, "logrite.ai_confidence": ai_confidence})
        return self.get_claim(claim_id)

    def write_audit(self, actor, action, claim_id, amount=None, outcome=None, notes=None):
        logger.debug(">>> Entering write_audit(actor=%s,action=%s,claim_id=%s,amount=%s,outcome=%s,notes=%s)", actor, action, claim_id, amount, outcome, notes, extra={"event.action": "write_audit", "user.name": str(actor), "logrite.action": action, "logrite.claim_id": claim_id, "logrite.amount": amount, "logrite.outcome": outcome, "logrite.notes": notes})
        __log_start = time.time()
        with self._connect() as conn:
            logger.debug("<<< Exiting write_audit(actor=%s,action=%s,claim_id=%s,amount=%s,outcome=%s,notes=%s)", actor, action, claim_id, amount, outcome, notes, extra={"event.action": "write_audit", "user.name": str(actor), "logrite.action": action, "logrite.claim_id": claim_id, "logrite.amount": amount, "logrite.outcome": outcome, "logrite.notes": notes})
            conn.execute(
                "INSERT INTO claims_audit (ts, actor, action, claim_id, amount, outcome, notes) VALUES (?,?,?,?,?,?,?)",
                (time.time(), actor, action, claim_id, amount, outcome, notes),
            )
            logger.info("write_audit(actor,action,claim_id,amount,outcome,notes)=%s,%s,%s,%s,%s,%s: save operation took %s ms", actor, action, claim_id, amount, outcome, notes, int((time.time() - __log_start) * 1000), extra={"event.action": "write_audit", "event.category": "database", "user.name": str(actor), "logrite.action": action, "logrite.claim_id": claim_id, "logrite.amount": amount, "logrite.outcome": outcome, "logrite.notes": notes})

    def list_audit(self, limit=100):
        logger.debug(">>> Entering list_audit(limit=%s)", limit, extra={"event.action": "list_audit", "logrite.limit": limit})
        __log_start = time.time()
        with self._connect() as conn:
            logger.debug("<<< Exiting list_audit(limit=%s)", limit, extra={"event.action": "list_audit", "logrite.limit": limit})
            rows = conn.execute("SELECT * FROM claims_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        logger.debug("list_audit(limit=%s): rows → %s", limit, rows, extra={"event.action": "list_audit", "logrite.limit": limit})
        logger.info("list_audit(limit)=%s: find operation took %s ms", limit, int((time.time() - __log_start) * 1000), extra={"event.action": "list_audit", "event.category": "database", "logrite.limit": limit})
        return [dict(r) for r in rows]
