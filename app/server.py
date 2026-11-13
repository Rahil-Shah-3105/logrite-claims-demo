import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from app import config
from app.logging_config import configure_logging
from app.services.ai_client import AIBlockedError, AIClientError
from app.services.claims_service import ClaimNotFound, ClaimsService, InvalidTransition, ValidationError

access_log = logging.getLogger("http.access")

INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Claims Demo</title>
<style>body{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:900px;margin:32px auto;padding:0 16px;color:#14171e}
h1{font-size:1.4rem}form,table{margin:16px 0}input,select,button{font:inherit;padding:6px 8px;margin:2px}
table{border-collapse:collapse;width:100%;font-size:.9rem}td,th{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left}
button.s{padding:3px 8px;font-size:.8rem}code{background:#f3f2ef;padding:1px 4px;border-radius:3px}.msg{color:#a83a2a;min-height:1.2em}</style></head>
<body><h1>Claims Demo (LogRite + Elastic use case 1)</h1>
<p>Submit a claim, adjudicate it with the AI agent, approve or override, then release payout. Actor header: <code id="actor">provider-1</code>
<select id="actorsel"><option>provider-1</option><option>reviewer-1</option><option>supervisor-1</option><option>batch-job</option></select></p>
<form id="f"><input name="provider_id" value="PRV-2201" placeholder="provider"> <input name="beneficiary_id" value="BEN-7731" placeholder="beneficiary">
<input name="procedure_code" value="99214" placeholder="procedure"> <input name="amount" value="1250" placeholder="amount" type="number" step="0.01"><br>
<textarea name="clinical_notes" rows="3" style="width:100%;max-width:880px;margin-top:6px" placeholder="Clinical notes attached by the provider (free text, sent to the AI agent)"></textarea><br><button>Submit claim</button></form>
<div class="msg" id="msg"></div>
<table><thead><tr><th>Claim</th><th>Provider</th><th>Amount</th><th>Notes</th><th>Status</th><th>AI</th><th>Actions</th></tr></thead><tbody id="rows"></tbody></table>
<script>
const $=s=>document.querySelector(s);const actor=()=>$('#actorsel').value;
$('#actorsel').onchange=()=>$('#actor').textContent=actor();
async function api(path,method,body){const r=await fetch(path,{method:method||'GET',headers:{'Content-Type':'application/json','X-Actor':actor()},body:body?JSON.stringify(body):undefined});
const t=await r.json();if(!r.ok){$('#msg').textContent=(t.error||'error')+(t.detail?': '+t.detail:'');}else{$('#msg').textContent='';}return t;}
async function load(){const c=await api('/claims');$('#rows').innerHTML=c.map(x=>`<tr><td><code>${x.claim_id}</code></td><td>${x.provider_id}</td><td>${x.amount.toFixed(2)}</td><td title="${(x.clinical_notes||'').replace(/"/g,'&quot;')}" style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#4a4f5a">${x.clinical_notes||''}</td><td>${x.status}</td><td>${x.ai_decision||''}${x.ai_confidence?' ('+x.ai_confidence+')':''}</td>
<td>${x.status==='SUBMITTED'?`<button class=s onclick="act('${x.claim_id}','adjudicate')">Adjudicate</button>`:''}
${x.status==='AI_APPROVED'?`<button class=s onclick="act('${x.claim_id}','approve')">Approve</button>`:''}${(x.status==='AI_APPROVED'||x.status==='AI_DENIED')?` <button class=s onclick="act('${x.claim_id}','payout-direct')" title="Pays without a human approval step">Pay without approval</button>`:''}
${x.status==='AI_DENIED'?`<button class=s onclick="act('${x.claim_id}','override')">Override</button>`:''}
${x.status==='APPROVED'?`<button class=s onclick="act('${x.claim_id}','payout')">Release payout</button>`:''}
${x.status==='PAID'?'<span style="color:#2f7d4f">Paid, complete</span>':''}${x.status==='PAYOUT_BLOCKED'?'<span style="color:#a83a2a">Payout blocked by AI governance relay</span>':''}${x.status==='ADJUDICATION_BLOCKED'?'<span style="color:#a83a2a">Adjudication blocked by AI governance relay</span>':''}${x.status==='PAYOUT_REFUSED'?'<span style="color:#a83a2a">Payout refused by model</span>':''}${x.status==='AI_DENIED'?'<span style="color:#7d828d">Denied by AI, awaiting supervisor</span> ':''}</td></tr>`).join('');}
async function act(id,a){await api('/claims/'+id+'/'+a,'POST',a==='override'?{justification:'supervisor review, documentation supplied'}:{});load();}
$('#f').onsubmit=async e=>{e.preventDefault();const d=Object.fromEntries(new FormData(e.target));d.amount=parseFloat(d.amount);await api('/claims','POST',d);load();};
load();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    service = ClaimsService()

    def log_message(self, fmt, *args):
        access_log.info("%s %s", self.address_string(), fmt % args)

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    def _actor(self):
        return self.headers.get("X-Actor", "anonymous")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/claims":
            return self._json(200, self.service.list_claims())
        if path == "/audit":
            return self._json(200, self.service.list_audit())
        if path.startswith("/claims/"):
            try:
                return self._json(200, self.service.get_claim(path.split("/")[2]))
            except ClaimNotFound:
                return self._json(404, {"error": "claim not found"})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        parts = path.strip("/").split("/")
        actor = self._actor()
        data = self._body()
        try:
            if path == "/claims":
                claim = self.service.submit_claim(
                    actor, data.get("provider_id", "PRV-0000"), data.get("beneficiary_id", "BEN-0000"),
                    data.get("procedure_code", "00000"), data.get("amount", 0), data.get("clinical_notes", ""))
                return self._json(201, claim)
            if len(parts) == 3 and parts[0] == "claims":
                claim_id, action = parts[1], parts[2]
                if action == "adjudicate":
                    return self._json(200, self.service.adjudicate(actor, claim_id))
                if action == "approve":
                    return self._json(200, self.service.approve(actor, claim_id))
                if action == "override":
                    return self._json(200, self.service.override(actor, claim_id, data.get("justification", "")))
                if action == "payout":
                    return self._json(200, self.service.release_payout(actor, claim_id))
                if action == "payout-direct":
                    return self._json(200, self.service.release_payout_direct(actor, claim_id))
            return self._json(404, {"error": "not found"})
        except ClaimNotFound:
            return self._json(404, {"error": "claim not found"})
        except ValidationError as exc:
            return self._json(400, {"error": "invalid claim", "detail": str(exc)})
        except InvalidTransition as exc:
            return self._json(409, {"error": "invalid transition", "detail": str(exc)})
        except AIBlockedError as exc:
            return self._json(403, {"error": "blocked by AI governance relay", "detail": str(exc)[:300]})
        except AIClientError as exc:
            return self._json(502, {"error": "AI adjudication failed", "detail": str(exc)[:300]})


def main():
    configure_logging()
    server = ThreadingHTTPServer(("127.0.0.1", config.APP_PORT), Handler)
    logging.getLogger("server").info("claims demo listening on http://127.0.0.1:%s", config.APP_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
