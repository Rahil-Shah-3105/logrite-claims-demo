import json
import re
import uuid

from app import config
from app.repositories.claims_repository import ClaimsRepository
from app.services.ai_client import AIClient, AIBlockedError


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
        self.repo = repository or ClaimsRepository()
        self.ai = ai_client or AIClient()

    def submit_claim(self, actor, provider_id, beneficiary_id, procedure_code, amount, clinical_notes=""):
        if not PROVIDER_ID_PATTERN.match(str(provider_id)):
            raise ValidationError("provider_id must look like PRV-1234")
        if not BENEFICIARY_ID_PATTERN.match(str(beneficiary_id)):
            raise ValidationError("beneficiary_id must look like BEN-1234")
        if not PROCEDURE_CODE_PATTERN.match(str(procedure_code)):
            raise ValidationError("procedure_code must be five digits")
        clinical_notes = (clinical_notes or "").strip()[:2000]
        claim = self.repo.create_claim(provider_id, beneficiary_id, procedure_code, float(amount), clinical_notes)
        self.repo.write_audit(actor, "SUBMIT", claim["claim_id"], claim["amount"], "SUBMITTED")
        return claim

    def adjudicate(self, actor, claim_id):
        claim = self._require(claim_id)
        if claim["status"] != "SUBMITTED":
            raise InvalidTransition("claim %s is %s, expected SUBMITTED" % (claim_id, claim["status"]))
        request_id = uuid.uuid4().hex
        facts = (
            "claim_id=%s provider_id=%s beneficiary_id=%s procedure_code=%s amount=%.2f\nclinical_notes: %s"
            % (claim["claim_id"], claim["provider_id"], claim["beneficiary_id"], claim["procedure_code"], claim["amount"],
               claim.get("clinical_notes") or "(none attached)")
        )
        try:
            raw = self.ai.complete(ADJUDICATION_SYSTEM_PROMPT, facts, request_id)
        except AIBlockedError as exc:
            self.repo.update_status(claim_id, "ADJUDICATION_BLOCKED")
            self.repo.write_audit(actor, "ADJUDICATE", claim_id, claim["amount"], "BLOCKED", str(exc)[:200])
            raise
        decision, confidence, reason = self._parse_decision(raw)
        status = "AI_APPROVED" if decision == "APPROVE" else "AI_DENIED"
        claim = self.repo.update_status(claim_id, status, ai_decision=decision, ai_confidence=confidence)
        self.repo.write_audit(actor, "ADJUDICATE", claim_id, claim["amount"], decision, reason)
        return claim

    def approve(self, actor, claim_id):
        claim = self._require(claim_id)
        if claim["status"] != "AI_APPROVED":
            raise InvalidTransition("claim %s is %s, expected AI_APPROVED" % (claim_id, claim["status"]))
        claim = self.repo.update_status(claim_id, "APPROVED")
        self.repo.write_audit(actor, "APPROVE", claim_id, claim["amount"], "APPROVED")
        return claim

    def override(self, actor, claim_id, justification):
        claim = self._require(claim_id)
        if claim["status"] != "AI_DENIED":
            raise InvalidTransition("claim %s is %s, expected AI_DENIED" % (claim_id, claim["status"]))
        claim = self.repo.update_status(claim_id, "APPROVED")
        self.repo.write_audit(actor, "OVERRIDE", claim_id, claim["amount"], "APPROVED", justification)
        return claim

    def release_payout(self, actor, claim_id):
        claim = self._require(claim_id)
        if claim["status"] != "APPROVED":
            raise InvalidTransition("claim %s is %s, expected APPROVED" % (claim_id, claim["status"]))
        request_id = uuid.uuid4().hex
        instruction = "PAYOUT claim_id=%s provider_id=%s amount=%.2f policy_ceiling=%.2f" % (
            claim["claim_id"], claim["provider_id"], claim["amount"], config.POLICY_PAYOUT_CEILING)
        try:
            raw = self.ai.complete(PAYOUT_SYSTEM_PROMPT, instruction, request_id)
        except AIBlockedError as exc:
            self.repo.update_status(claim_id, "PAYOUT_BLOCKED")
            self.repo.write_audit(actor, "PAYOUT", claim_id, claim["amount"], "BLOCKED", str(exc)[:200])
            raise
        authorized = self._parse_authorization(raw)
        status = "PAID" if authorized else "PAYOUT_REFUSED"
        claim = self.repo.update_status(claim_id, status)
        self.repo.write_audit(actor, "PAYOUT", claim_id, claim["amount"], status)
        return claim

    def release_payout_direct(self, actor, claim_id):
        """Batch-style payout that skips the human approve/override step (simulates a misconfigured integration)."""
        claim = self._require(claim_id)
        if claim["status"] not in ("AI_APPROVED", "AI_DENIED"):
            raise InvalidTransition("claim %s is %s, expected AI_APPROVED or AI_DENIED" % (claim_id, claim["status"]))
        self.repo.update_status(claim_id, "APPROVED")
        self.repo.write_audit(actor, "AUTO_APPROVE", claim_id, claim["amount"], "APPROVED", "batch payout, no human approval")
        claim = self.release_payout(actor, claim_id)
        return claim

    def get_claim(self, claim_id):
        return self._require(claim_id)

    def list_claims(self):
        return self.repo.list_claims()

    def list_audit(self):
        return self.repo.list_audit()

    def _require(self, claim_id):
        claim = self.repo.get_claim(claim_id)
        if claim is None:
            raise ClaimNotFound(claim_id)
        return claim

    @staticmethod
    def _parse_decision(raw):
        try:
            data = json.loads(raw.strip().strip("`").replace("json\n", "", 1))
            return data.get("decision", "DENY").upper(), float(data.get("confidence", 0)), data.get("reason", "")
        except (ValueError, AttributeError):
            return "DENY", 0.0, "unparseable model response"

    @staticmethod
    def _parse_authorization(raw):
        try:
            data = json.loads(raw.strip().strip("`").replace("json\n", "", 1))
            return bool(data.get("authorized", False))
        except (ValueError, AttributeError):
            return False
