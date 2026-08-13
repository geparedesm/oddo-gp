#!/usr/bin/env bash

set -euo pipefail

DB_HOST="${ODOO_DB_HOST:-db}"
DB_PORT="${ODOO_DB_PORT:-5432}"
DB_USER="${ODOO_DB_USER:-odoo}"
DB_PASSWORD="${ODOO_DB_PASSWORD:-odoo}"
DB_NAME="${ODOO_DB_NAME:-odoo16}"

export PGPASSWORD="${DB_PASSWORD}"

until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres >/dev/null 2>&1; do
  echo "[entrypoint] waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}"
  sleep 2
done

db_exists="$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'")"
if [[ "${db_exists}" != "1" ]]; then
  echo "[entrypoint] creating database ${DB_NAME}"
  createdb -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" "${DB_NAME}"
fi

base_ready="$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='ir_module_module'")"
if [[ "${base_ready}" != "1" ]]; then
  echo "[entrypoint] initializing Odoo base modules in ${DB_NAME}"
  odoo -c /etc/odoo/odoo.conf -d "${DB_NAME}" -i base --without-demo=all --stop-after-init
fi

exec odoo -c /etc/odoo/odoo.conf -d "${DB_NAME}" --dev=reload,xml,qweb
