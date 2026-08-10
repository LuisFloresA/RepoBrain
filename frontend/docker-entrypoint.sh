#!/bin/sh
# Entrypoint de nginx no-root: lanza nginx como appuser (pid en /tmp vía nginx-main.conf).
set -eu

exec nginx -g 'daemon off;'