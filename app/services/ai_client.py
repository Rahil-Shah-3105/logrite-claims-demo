import json
import urllib.error
import urllib.request

from app import config
import time
import logging
logger = logging.getLogger(__name__)


class AIClientError(Exception):
    pass


class AIBlockedError(AIClientError):
    """Raised when the relay refuses the call (Warden verdict: Block)."""


class AIClient:
    """Calls an OpenAI-compatible chat completions endpoint.

    With AI_BASE_URL unset, a deterministic stub stands in for the model so the
    app runs without any provider. Point AI_BASE_URL at a provider or at the
    Warden relay and the same code path is used.
    """

    def __init__(self, base_url=None, api_key=None, model=None):
        logger.debug(">>> Entering __init__(base_url=%s,api_key=<redacted>,model=%s)", base_url, model, extra={"event.action": "__init__", "logrite.base_url": base_url, "logrite.model": model})
        self.base_url = base_url if base_url is not None else config.AI_BASE_URL
        logger.debug("__init__(self=%s,base_url=%s,api_key=<redacted>,model=%s): self.base_url → %s", self, base_url, model, self.base_url, extra={"event.action": "__init__", "logrite.base_url": base_url, "logrite.model": model})
        self.api_key = api_key if api_key is not None else config.AI_API_KEY
        logger.debug("__init__(self=%s,base_url=%s,api_key=<redacted>,model=%s): self.api_key → <redacted>", self, base_url, model, extra={"event.action": "__init__", "logrite.base_url": base_url, "logrite.model": model})
        self.model = model or config.AI_MODEL
        logger.debug("<<< Exiting __init__(base_url=%s,api_key=<redacted>,model=%s)", base_url, model, extra={"event.action": "__init__", "logrite.base_url": base_url, "logrite.model": model})
        logger.debug("__init__(self=%s,base_url=%s,api_key=<redacted>,model=%s): self.model → %s", self, base_url, model, self.model, extra={"event.action": "__init__", "logrite.base_url": base_url, "logrite.model": model})

    def complete(self, system_prompt, user_prompt, request_id):
        logger.debug(">>> Entering complete(system_prompt=<redacted>,user_prompt=<redacted>,request_id=%s)", request_id, extra={"event.action": "complete", "logrite.request_id": request_id})
        if not self.base_url:
            return self._stub(user_prompt)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.api_key,
                "X-Request-ID": request_id,
                "User-Agent": "claims-demo/1.0 (+https://github.com/beelizdean/logrite-claims-demo)",
                "Accept": "application/json",
            },
            method="POST",
        )
        __log_start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            logger.error("Exception in complete(system_prompt=<redacted>,user_prompt=<redacted>,request_id=%s): %s", request_id, str(exc), exc_info=True, extra={"event.action": "complete", "event.category": "process", "logrite.request_id": request_id})
            detail = exc.read().decode("utf-8", "replace")
            logger.info("complete(system_prompt,user_prompt,request_id)=<redacted>,<redacted>,%s: external service call took %s ms", request_id, int((time.time() - __log_start) * 1000), extra={"event.action": "complete", "event.category": "network", "logrite.request_id": request_id})
            if exc.code in (403, 422, 451):
                raise AIBlockedError(detail)
            raise AIClientError("HTTP %s: %s" % (exc.code, detail))
        except urllib.error.URLError as exc:
            raise AIClientError(str(exc))
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            logger.error("Exception in complete(system_prompt=<redacted>,user_prompt=<redacted>,request_id=%s)", request_id, exc_info=True, extra={"event.action": "complete", "event.category": "process", "logrite.request_id": request_id})
            logger.debug("<<< Exiting complete(system_prompt=<redacted>,user_prompt=<redacted>,request_id=%s)", request_id, extra={"event.action": "complete", "logrite.request_id": request_id})
            raise AIClientError("unexpected response shape: %s" % json.dumps(body)[:200])

    @staticmethod
    def _stub(user_prompt):
        logger.debug(">>> Entering _stub(user_prompt=<redacted>)", extra={"event.action": "_stub"})
        amount = 0.0
        logger.warning("_stub(user_prompt=<redacted>): amount → %s", amount, extra={"event.action": "_stub"})
        for token in user_prompt.replace(",", " ").split():
            if token.startswith("amount="):
                try:
                    amount = float(token.split("=", 1)[1])
                except ValueError:
                    logger.error("Exception in _stub(user_prompt=<redacted>)", exc_info=True, extra={"event.action": "_stub", "event.category": "process"})
                    pass
        if "PAYOUT" in user_prompt:
            return json.dumps({"authorized": True, "reason": "stub model authorizes all payouts"})
        if amount <= 5000:
            return json.dumps({"decision": "APPROVE", "confidence": 0.91, "reason": "routine procedure within range"})
        logger.debug("<<< Exiting _stub(user_prompt=<redacted>)", extra={"event.action": "_stub"})
        return json.dumps({"decision": "DENY", "confidence": 0.78, "reason": "amount above routine threshold"})
