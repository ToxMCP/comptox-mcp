#!/usr/bin/env sh
set -euo pipefail

APP_MODULE="${APP_MODULE:-epacomp_tox.transport.websocket:app}"
GUNICORN_CONF="${GUNICORN_CONF:-/app/gunicorn_conf.py}"

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec gunicorn "$APP_MODULE" -c "$GUNICORN_CONF"
