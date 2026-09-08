#!/bin/sh
# Ships logs/app.log to Elastic Cloud using Filebeat running directly on this Mac.
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
[ -z "$ELASTIC_ENDPOINT" ] && { echo "ELASTIC_ENDPOINT is empty in .env"; exit 1; }
case "$ELASTIC_API_KEY" in *:*) ;; *) ELASTIC_API_KEY=$(printf '%s' "$ELASTIC_API_KEY" | base64 -d 2>/dev/null || echo "$ELASTIC_API_KEY");; esac
export ELASTIC_API_KEY
export APP_LOG="$PWD/logs/app.log" FB_DATA="$PWD/filebeat/native/data"
mkdir -p "$FB_DATA"
if [ -f filebeat/native/.pid ] && kill -0 "$(cat filebeat/native/.pid)" 2>/dev/null; then echo "filebeat already running"; exit 0; fi
nohup ./filebeat/native/fb/filebeat -c "$PWD/filebeat/native/filebeat.yml" --strict.perms=false >> "$FB_DATA/stdout.log" 2>&1 &
echo $! > filebeat/native/.pid
echo "filebeat started (pid $(cat filebeat/native/.pid)); log at filebeat/native/data/logs/filebeat.log"
