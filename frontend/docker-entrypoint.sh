#!/bin/sh
# Entrypoint de nginx no-root: reescribe el pid y lanza nginx como appuser.
set -eu

exec nginx -g 'pid /tmp/nginx.pid; daemon off;' "$@"