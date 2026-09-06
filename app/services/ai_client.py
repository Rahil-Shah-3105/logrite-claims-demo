import json
import urllib.error
import urllib.request

from app import config
import logging
root = logging.getLogger()


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
        root.debug(">>> Entering __init__(base_url=%s,api_key=<redacted>,model=%s)", base_url, model)
        self.base_url = base_url if base_url is not None else config.AI_BASE_URL
        self.api_key = api_key if api_key is not None else config.AI_API_KEY
        self.model = model or config.AI_MODEL
        root.debug("<<< Exiting __init__(base_url=%s,api_key=<redacted>,model=%s)", base_url, model)

    def complete(self, system_prompt, user_prompt, request_id):
        root.debug(">>> Entering complete(system_prompt=%s,user_prompt=%s,request_id=%s)", system_prompt, user_prompt, request_id)
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
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                root.error("Exception in complete(system_prompt=%s,user_prompt=%s,request_id=%s): %s", system_prompt, user_prompt, request_id, str(exc), exc_info=True)
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            if exc.code in (403, 422, 451):
                raise AIBlockedError(detail)
            raise AIClientError("HTTP %s: %s" % (exc.code, detail))
        except urllib.error.URLError as exc:
            raise AIClientError(str(exc))
        try:
            root.debug("<<< Exiting complete(system_prompt=%s,user_prompt=%s,request_id=%s)", system_prompt, user_prompt, request_id)
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise AIClientError("unexpected response shape: %s" % json.dumps(body)[:200])

    @staticmethod
    def _stub(user_prompt):
        root.debug(">>> Entering _stub(user_prompt=%s)", user_prompt)
        root.debug("_stub(user_prompt=%s): amount → %s", user_prompt, amount)
        amount = 0.0
        for token in user_prompt.replace(",", " ").split():
            if token.startswith("amount="):
                try:
                    amount = float(token.split("=", 1)[1])
                except ValueError:
                    root.error("Exception in _stub(user_prompt=%s)", user_prompt, exc_info=True)
                    pass
        if "PAYOUT" in user_prompt:
            return json.dumps({"authorized": True, "reason": "stub model authorizes all payouts"})
        if amount <= 5000:
            return json.dumps({"decision": "APPROVE", "confidence": 0.91, "reason": "routine procedure within range"})
        return json.dumps({"decision": "DENY", "confidence": 0.78, "reason": "amount above routine threshold"})
