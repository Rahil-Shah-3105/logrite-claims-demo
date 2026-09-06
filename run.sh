#!/bin/sh
# Starts the claims demo in the background. Logs to logs/app.log. Stop with ./stop.sh
cd "$(dirname "$0")"
mkdir -p logs data
if [ -f .pid ] && kill -0 "$(cat .pid)" 2>/dev/null; then echo "already running (pid $(cat .pid))"; exit 0; fi
nohup /usr/bin/python3 -m app.server >> logs/server.out 2>&1 &
echo $! > .pid
sleep 1
echo "started pid $(cat .pid); open http://127.0.0.1:${APP_PORT:-8088}"
