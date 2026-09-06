# Claims demo (LogRite + Elastic, use case 1)

A deliberately under-logged claims service: submit, AI adjudicate, approve or override, release payout, with a `claims_audit` table.
Runs on the Python that ships with macOS. No packages to install.

    ./run.sh                     # start on http://127.0.0.1:8088
    /usr/bin/python3 seed.py     # seed claims and one bad audit row
    scripts/demo_claims.sh       # run the three demo claims
    ./stop.sh

Config lives in `.env` (copy from `.env.example`). Leave `AI_BASE_URL` empty to use the built-in stub model;
set it to a provider or to the Warden relay to route adjudication and payout through a real model.

Ship logs to Elastic Cloud with `filebeat/start.sh` after filling `ELASTIC_ENDPOINT` and `ELASTIC_API_KEY` in `.env`.
