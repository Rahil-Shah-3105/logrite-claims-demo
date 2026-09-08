#!/bin/sh
# Runs the three demo claims: a clean approval, a denial, and a supervisor override, then payouts.
B=http://127.0.0.1:${APP_PORT:-8088}
post() { curl -s -X POST "$B$1" -H 'Content-Type: application/json' -H "X-Actor: $2" -d "$3"; }
id() { /usr/bin/python3 -c 'import sys,json;print(json.load(sys.stdin)["claim_id"])'; }

echo "1. clean approval"
C1=$(post /claims provider-1 '{"provider_id":"PRV-2201","beneficiary_id":"BEN-7731","procedure_code":"99214","amount":180}' | id)
post /claims/$C1/adjudicate system >/dev/null; post /claims/$C1/approve reviewer-1 >/dev/null; post /claims/$C1/payout system; echo; echo "   $C1"

echo "2. denial"
C2=$(post /claims provider-1 '{"provider_id":"PRV-2201","beneficiary_id":"BEN-8102","procedure_code":"99214","amount":9500}' | id)
post /claims/$C2/adjudicate system; echo; echo "   $C2"

echo "3. supervisor override then payout (above ceiling: Warden should block when relay is on)"
C3=$(post /claims provider-1 '{"provider_id":"PRV-3390","beneficiary_id":"BEN-1044","procedure_code":"27447","amount":24900}' | id)
post /claims/$C3/adjudicate system >/dev/null; post /claims/$C3/override supervisor-1 '{"justification":"supervisor review, documentation supplied"}' >/dev/null; post /claims/$C3/payout system; echo; echo "   $C3"
