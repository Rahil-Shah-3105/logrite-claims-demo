#!/bin/sh
cd "$(dirname "$0")"
[ -f .pid ] && kill "$(cat .pid)" 2>/dev/null && rm -f .pid && echo stopped || echo "not running"
