#!/bin/sh
cd "$(dirname "$0")/.."
[ -f filebeat/native/.pid ] && kill "$(cat filebeat/native/.pid)" 2>/dev/null && rm -f filebeat/native/.pid && echo "filebeat stopped" || echo "filebeat not running"
