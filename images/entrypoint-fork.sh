#!/bin/sh
set -e
# Wait for PostgreSQL using the same env vars as the official Odoo image.
HOST="${HOST:-db}"
PORT="${PORT:-5432}"
USER="${USER:-odoo}"
export PGPASSWORD="${PASSWORD:-odoo}"
i=0
until pg_isready -h "$HOST" -p "$PORT" -U "$USER" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "postgres not ready" >&2
    exit 1
  fi
  sleep 2
done
if [ "$#" -eq 0 ]; then
  exec odoo --config="${ODOO_RC:-/etc/odoo/odoo.conf}"
fi
exec "$@"
