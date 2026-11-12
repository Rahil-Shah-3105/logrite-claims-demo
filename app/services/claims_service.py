import json
import re
import uuid

from app import config
from app.repositories.claims_repository import ClaimsRepository
from app.services.ai_client import AIClient, AIBlockedError
import logging
root = logging.getLogger()
import time


ADJUDICATION_SYSTEM_PROMPT = (
    "You are a claims adjudication agent for a public health insurance program. "
    "Given claim facts and the clinical notes attached by the provider, respond with JSON only: "
    '{"decision": "APPROVE" or "DENY", "confidence": 0-1, "reason": short text}. '
    "Deny claims with implausible amounts for the procedure, missing eligibility, or notes that do not support the procedure."
)

PROVIDER_ID_PATTERN = re.compile(r"^PRV-\d{4}$")
BENEFICIARY_ID_PATTERN = re.compile(r"^BEN-\d{4}$")
PROCEDURE_CODE_PATTERN = re.compile(r"^\d{5}$")

PAYOUT_SYSTEM_PROMPT = (
    "You are a payment authorization agent. Given a payout instruction, respond with JSON only: "
    '{"authorized": true or false, "reason": short text}.'
)


class ClaimNotFound(Exception):
    pass


class ValidationError(Exception):
    pass


class InvalidTransition(Exception):
    pass


class ClaimsService:
    """Business logic for the claims lifecycle: submit, adjudicate, approve, override, payout."""

    def __init__(self, repository=None, ai_client=None):
        root.debug(">>> Entering __init__(repository=%s,ai_client=%s)", repository, ai_client, extra={"event.action": "__init__", "logrite.repository": repository, "logrite.ai_client": ai_client})
        self.repo = repository or ClaimsRepository()
        root.debug("__init__(repository=%s,ai_client=%s): self.repo → %s", repository, ai_client, self.repo, extra={"event.action": "__init__", "logrite.repository": repository, "logrite.ai_client": ai_client})
        self.ai = ai_client or AIClient()
        root.debug("<<< Exiting __init__(repository=%s,ai_client=%s)", repository, ai_client, extra={"event.action": "__init__", "logrite.repository": repository, "logrite.ai_client": ai_client})
        root.debug("__init__(repository=%s,ai_client=%s): self.ai → %s", repository, ai_client, self.ai, extra={"event.action": "__init__", "logrite.repository": repository, "logrite.ai_client": ai_client})

    def submit_claim(self, actor, provider_id, beneficiary_id, procedure_code, amount, clinical_notes=""):
        root.debug(">>> Entering submit_claim(actor=%s,provider_id=<redacted>,beneficiary_id=<redacted>,procedure_code=%s,amount=%s,clinical_notes=<redacted>)", actor, procedure_code, amount, extra={"event.action": "submit_claim", "user.name": str(actor), "logrite.procedure_code": procedure_code, "logrite.amount": amount})
        if not PROVIDER_ID_PATTERN.match(str(provider_id)):
            raise ValidationError("provider_id must look like PRV-1234")
        if not BENEFICIARY_ID_PATTERN.match(str(beneficiary_id)):
            raise ValidationError("beneficiary_id must look like BEN-1234")
        if not PROCEDURE_CODE_PATTERN.match(str(procedure_code)):
            raise ValidationError("procedure_code must be five digits")
        clinical_notes = (clinical_notes or "").strip()[:2000]
        root.debug("submit_claim(actor=%s,provider_id=<redacted>,beneficiary_id=<redacted>,procedure_code=%s,amount=%s,clinical_notes=<redacted>): clinical_notes → <redacted>", actor, procedure_code, amount, extra={"event.action": "submit_claim", "user.name": str(actor), "logrite.procedure_code": procedure_code, "logrite.amount": amount})
        claim = self.repo.create_claim(provider_id, beneficiary_id, procedure_code, float(amount), clinical_notes)
        root.debug("submit_claim(self=%s,actor=%s,provider_id=<redacted>,beneficiary_id=<redacted>,procedure_code=%s,amount=%s,clinical_notes=<redacted>): claim → %s", self, actor, procedure_code, amount, claim, extra={"event.action": "submit_claim", "user.name": str(actor), "logrite.procedure_code": procedure_code, "logrite.amount": amount})
        root.debug("submit_claim(actor=%s,provider_id=<redacted>,beneficiary_id=<redacted>,procedure_code=%s,amount=%s,clinical_notes=<redacted>): claim → %s", actor, procedure_code, amount, claim, extra={"event.action": "submit_claim", "user.name": str(actor), "logrite.procedure_code": procedure_code, "logrite.amount": amount})
        self.repo.write_audit(actor, "SUBMIT", claim["claim_id"], claim["amount"], "SUBMITTED")
        root.debug("<<< Exiting submit_claim(actor=%s,provider_id=<redacted>,beneficiary_id=<redacted>,procedure_code=%s,amount=%s,clinical_notes=<redacted>)", actor, procedure_code, amount, extra={"event.action": "submit_claim", "user.name": str(actor), "logrite.procedure_code": procedure_code, "logrite.amount": amount})
        return claim

    def adjudicate(self, actor, claim_id):
        root.debug(">>> Entering adjudicate(actor=%s,claim_id=%s)", actor, claim_id, extra={"event.action": "adjudicate", "user.name": str(actor), "logrite.claim_id": claim_id})
        claim = self._require(claim_id)
        root.debug("adjudicate(self=%s,actor=%s,claim_id=%s): claim → %s", self, actor, claim_id, claim, extra={"event.action": "adjudicate", "user.name": str(actor), "logrite.claim_id": claim_id})
        root.debug("adjudicate(actor=%s,claim_id=%s): claim → %s", actor, claim_id, claim, extra={"event.action": "adjudicate", "user.name": str(actor), "logrite.claim_id": claim_id})
        if claim["status"] != "SUBMITTED":
            raise InvalidTransition("claim %s is %s, expected SUBMITTED" % (claim_id, claim["status"]))
            root.error("Exception in adjudicate(actor=%s,claim_id=%s)", actor, claim_id, exc_info=True, extra={"event.action": "adjudicate", "event.category": "process", "user.name": str(actor), "logrite.claim_id": claim_id})
        request_id = uuid.uuid4().hex
        root.debug("adjudicate(self=%s,actor=%s,claim_id=%s): request_id → %s", self, actor, claim_id, request_id, extra={"event.action": "adjudicate", "user.name": str(actor), "logrite.claim_id": claim_id})
        facts = (
            "claim_id=%s provider_id=%s beneficiary_id=%s procedure_code=%s amount=%.2f\nclinical_notes: %s"
            % (claim["claim_id"], claim["provider_id"], claim["beneficiary_id"], claim["procedure_code"], claim["amount"],
               claim.get("clinical_notes") or "(none attached)")
        )
        root.debug("adjudicate(actor=%s,claim_id=%s): request_id → %s", actor, claim_id, request_id, extra={"event.action": "adjudicate", "user.name": str(actor), "logrite.claim_id": claim_id})
        root.debug("adjudicate(self=%s,actor=%s,claim_id=%s): facts → %s", self, actor, claim_id, facts, extra={"event.action": "adjudicate", "user.name": str(actor), "logrite.claim_id": claim_id})
        try:
            raw = self.ai.complete(ADJUDICATION_SYSTEM_PROMPT, facts, request_id)
        except AIBlockedError as exc:
            __log_start = time.time()
            self.repo.update_status(claim_id, "ADJUDICATION_BLOCKED")
            self.repo.write_audit(actor, "ADJUDICATE", claim_id, claim["amount"], "BLOCKED", str(exc)[:200])
            root.info("adjudicate(actor,claim_id)=%s,%s: update operation took %s ms", actor, claim_id, int((time.time() - __log_start) * 1000), extra={"event.action": "adjudicate", "event.category": "database", "user.name": str(actor), "logrite.claim_id": claim_id})
            raise
        decision, confidence, reason = self._parse_decision(raw)
        status = "AI_APPROVED" if decision == "APPROVE" else "AI_DENIED"
        root.debug("adjudicate(actor=%s,claim_id=%s): status → %s", actor, claim_id, status, extra={"event.action": "adjudicate", "user.name": str(actor), "logrite.claim_id": claim_id})
        claim = self.repo.update_status(claim_id, status, ai_decision=decision, ai_confidence=confidence)
        self.repo.write_audit(actor, "ADJUDICATE", claim_id, claim["amount"], decision, reason)
        root.debug("<<< Exiting adjudicate(actor=%s,claim_id=%s)", actor, claim_id, extra={"event.action": "adjudicate", "user.name": str(actor), "logrite.claim_id": claim_id})
        return claim

    def approve(self, actor, claim_id):
        root.debug(">>> Entering approve(actor=%s,claim_id=%s)", actor, claim_id, extra={"event.action": "approve", "user.name": str(actor), "logrite.claim_id": claim_id})
        claim = self._require(claim_id)
        root.debug("approve(self=%s,actor=%s,claim_id=%s): claim → %s", self, actor, claim_id, claim, extra={"event.action": "approve", "user.name": str(actor), "logrite.claim_id": claim_id})
        root.debug("approve(actor=%s,claim_id=%s): claim → %s", actor, claim_id, claim, extra={"event.action": "approve", "user.name": str(actor), "logrite.claim_id": claim_id})
        if claim["status"] != "AI_APPROVED":
            raise InvalidTransition("claim %s is %s, expected AI_APPROVED" % (claim_id, claim["status"]))
        claim = self.repo.update_status(claim_id, "APPROVED")
        self.repo.write_audit(actor, "APPROVE", claim_id, claim["amount"], "APPROVED")
        root.debug("<<< Exiting approve(actor=%s,claim_id=%s)", actor, claim_id, extra={"event.action": "approve", "user.name": str(actor), "logrite.claim_id": claim_id})
        return claim

    def override(self, actor, claim_id, justification):
        root.debug(">>> Entering override(actor=%s,claim_id=%s,justification=%s)", actor, claim_id, justification, extra={"event.action": "override", "user.name": str(actor), "logrite.claim_id": claim_id, "logrite.justification": justification})
        claim = self._require(claim_id)
        root.debug("override(self=%s,actor=%s,claim_id=%s,justification=%s): claim → %s", self, actor, claim_id, justification, claim, extra={"event.action": "override", "user.name": str(actor), "logrite.claim_id": claim_id, "logrite.justification": justification})
        root.debug("override(actor=%s,claim_id=%s,justification=%s): claim → %s", actor, claim_id, justification, claim, extra={"event.action": "override", "user.name": str(actor), "logrite.claim_id": claim_id, "logrite.justification": justification})
        if claim["status"] != "AI_DENIED":
            raise InvalidTransition("claim %s is %s, expected AI_DENIED" % (claim_id, claim["status"]))
        claim = self.repo.update_status(claim_id, "APPROVED")
        self.repo.write_audit(actor, "OVERRIDE", claim_id, claim["amount"], "APPROVED", justification)
        root.debug("<<< Exiting override(actor=%s,claim_id=%s,justification=%s)", actor, claim_id, justification, extra={"event.action": "override", "user.name": str(actor), "logrite.claim_id": claim_id, "logrite.justification": justification})
        return claim

    def release_payout(self, actor, claim_id):
        root.debug(">>> Entering release_payout(actor=%s,claim_id=%s)", actor, claim_id, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
        claim = self._require(claim_id)
        root.debug("release_payout(self=%s,actor=%s,claim_id=%s): claim → %s", self, actor, claim_id, claim, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
        root.debug("release_payout(actor=%s,claim_id=%s): claim → %s", actor, claim_id, claim, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
        if claim["status"] != "APPROVED":
            raise InvalidTransition("claim %s is %s, expected APPROVED" % (claim_id, claim["status"]))
            root.error("Exception in release_payout(actor=%s,claim_id=%s)", actor, claim_id, exc_info=True, extra={"event.action": "release_payout", "event.category": "process", "user.name": str(actor), "logrite.claim_id": claim_id})
        request_id = uuid.uuid4().hex
        root.debug("release_payout(self=%s,actor=%s,claim_id=%s): request_id → %s", self, actor, claim_id, request_id, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
        instruction = "PAYOUT claim_id=%s provider_id=%s amount=%.2f policy_ceiling=%.2f" % (
            claim["claim_id"], claim["provider_id"], claim["amount"], config.POLICY_PAYOUT_CEILING)
        root.debug("release_payout(actor=%s,claim_id=%s): request_id → %s", actor, claim_id, request_id, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
        root.debug("release_payout(self=%s,actor=%s,claim_id=%s): instruction → %s", self, actor, claim_id, instruction, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
        try:
            raw = self.ai.complete(PAYOUT_SYSTEM_PROMPT, instruction, request_id)
        except AIBlockedError as exc:
            self.repo.update_status(claim_id, "PAYOUT_BLOCKED")
            self.repo.write_audit(actor, "PAYOUT", claim_id, claim["amount"], "BLOCKED", str(exc)[:200])
            root.debug("<<< Exiting release_payout(actor=%s,claim_id=%s)", actor, claim_id, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
            raise
        authorized = self._parse_authorization(raw)
        root.debug("release_payout(self=%s,actor=%s,claim_id=%s): authorized → %s", self, actor, claim_id, authorized, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
        root.debug("release_payout(actor=%s,claim_id=%s): authorized → %s", actor, claim_id, authorized, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
        status = "PAID" if authorized else "PAYOUT_REFUSED"
        claim = self.repo.update_status(claim_id, status)
        root.debug("release_payout(self=%s,actor=%s,claim_id=%s): status → %s", self, actor, claim_id, status, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
        root.debug("release_payout(actor=%s,claim_id=%s): status → %s", actor, claim_id, status, extra={"event.action": "release_payout", "user.name": str(actor), "logrite.claim_id": claim_id})
        self.repo.write_audit(actor, "PAYOUT", claim_id, claim["amount"], status)
        return claim

    def release_payout_direct(self, actor, claim_id):
        """Batch-style payout that skips the human approve/override step (simulates a misconfigured integration)."""
        root.debug(">>> Entering release_payout_direct(actor=%s,claim_id=%s)", actor, claim_id, extra={"event.action": "release_payout_direct", "user.name": str(actor), "logrite.claim_id": claim_id})
        claim = self._require(claim_id)
        root.debug("release_payout_direct(self=%s,actor=%s,claim_id=%s): claim → %s", self, actor, claim_id, claim, extra={"event.action": "release_payout_direct", "user.name": str(actor), "logrite.claim_id": claim_id})
        root.debug("release_payout_direct(actor=%s,claim_id=%s): claim → %s", actor, claim_id, claim, extra={"event.action": "release_payout_direct", "user.name": str(actor), "logrite.claim_id": claim_id})
        if claim["status"] not in ("AI_APPROVED", "AI_DENIED"):
            raise InvalidTransition("claim %s is %s, expected AI_APPROVED or AI_DENIED" % (claim_id, claim["status"]))
        self.repo.update_status(claim_id, "APPROVED")
        self.repo.write_audit(actor, "AUTO_APPROVE", claim_id, claim["amount"], "APPROVED", "batch payout, no human approval")
        root.debug("<<< Exiting release_payout_direct(actor=%s,claim_id=%s)", actor, claim_id, extra={"event.action": "release_payout_direct", "user.name": str(actor), "logrite.claim_id": claim_id})
        claim = self.release_payout(actor, claim_id)
        return claim

    def get_claim(self, claim_id):
        root.debug(">>> Entering get_claim(claim_id=%s)", claim_id, extra={"event.action": "get_claim", "logrite.claim_id": claim_id})
        root.debug("<<< Exiting get_claim(claim_id=%s)", claim_id, extra={"event.action": "get_claim", "logrite.claim_id": claim_id})
        return self._require(claim_id)

    def list_claims(self):
        root.debug(">>> Entering list_claims()", extra={"event.action": "list_claims"})
        root.debug("<<< Exiting list_claims()", extra={"event.action": "list_claims"})
        return self.repo.list_claims()

    def list_audit(self):
        root.debug(">>> Entering list_audit()", extra={"event.action": "list_audit"})
        root.debug("<<< Exiting list_audit()", extra={"event.action": "list_audit"})
        return self.repo.list_audit()

    def _require(self, claim_id):
        root.debug(">>> Entering _require(claim_id=%s)", claim_id, extra={"event.action": "_require", "logrite.claim_id": claim_id})
        claim = self.repo.get_claim(claim_id)
        root.debug("_require(self=%s,claim_id=%s): claim → %s", self, claim_id, claim, extra={"event.action": "_require", "logrite.claim_id": claim_id})
        root.debug("_require(claim_id=%s): claim → %s", claim_id, claim, extra={"event.action": "_require", "logrite.claim_id": claim_id})
        if claim is None:
            raise ClaimNotFound(claim_id)
        root.debug("<<< Exiting _require(claim_id=%s)", claim_id, extra={"event.action": "_require", "logrite.claim_id": claim_id})
        return claim

    @staticmethod
    def _parse_decision(raw):
        root.debug(">>> Entering _parse_decision(raw=%s)", raw, extra={"event.action": "_parse_decision", "logrite.raw": raw})
        try:
            data = json.loads(raw.strip().strip("`").replace("json\n", "", 1))
            root.debug("_parse_decision(raw=%s): data → %s", raw, data, extra={"event.action": "_parse_decision", "logrite.raw": raw})
            return data.get("decision", "DENY").upper(), float(data.get("confidence", 0)), data.get("reason", "")
        except (ValueError, AttributeError):
            root.error("Exception in _parse_decision(raw=%s)", raw, exc_info=True, extra={"event.action": "_parse_decision", "event.category": "process", "logrite.raw": raw})
            root.debug("<<< Exiting _parse_decision(raw=%s)", raw, extra={"event.action": "_parse_decision", "logrite.raw": raw})
            return "DENY", 0.0, "unparseable model response"

    @staticmethod
    def _parse_authorization(raw):
        root.debug(">>> Entering _parse_authorization(raw=<redacted>)", extra={"event.action": "_parse_authorization"})
        try:
            data = json.loads(raw.strip().strip("`").replace("json\n", "", 1))
            root.debug("_parse_authorization(raw=<redacted>): data → %s", data, extra={"event.action": "_parse_authorization"})
            return bool(data.get("authorized", False))
        except (ValueError, AttributeError):
            root.error("Exception in _parse_authorization(raw=<redacted>)", exc_info=True, extra={"event.action": "_parse_authorization", "event.category": "process"})
            root.debug("<<< Exiting _parse_authorization(raw=<redacted>)", extra={"event.action": "_parse_authorization"})
            return False
