#!/bin/sh
# Ships logs/app.log to Elastic Cloud. Reads ELASTIC_ENDPOINT and ELASTIC_API_KEY from ../.env
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
[ -z "$ELASTIC_ENDPOINT" ] && { echo "ELASTIC_ENDPOINT is empty in .env"; exit 1; }
# Beats want the api key as id:secret. If .env holds the base64 "encoded" form, decode it.
case "$ELASTIC_API_KEY" in
  *:*) ;;
  *) ELASTIC_API_KEY=$(printf '%s' "$ELASTIC_API_KEY" | base64 -d 2>/dev/null || echo "$ELASTIC_API_KEY");;
esac
export ELASTIC_API_KEY
docker rm -f claims-filebeat >/dev/null 2>&1
docker run -d --name claims-filebeat \
  -e ELASTIC_ENDPOINT -e ELASTIC_API_KEY \
  -v "$PWD/filebeat/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro" \
  -v "$PWD/logs:/logs:ro" \
  docker.elastic.co/beats/filebeat:9.1.0 filebeat -e --strict.perms=false
echo "filebeat started; docker logs -f claims-filebeat to watch"
