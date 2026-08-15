#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

set -a
source ./.env
set +a

odoo_url="http://127.0.0.1:${ODOO_HTTP_PORT}"

docker compose restart odoo

for _ in {1..30}; do
  if curl --fail --silent --show-error "${odoo_url}/web/login?db=${ODOO_DB_NAME}" >/dev/null; then
    echo "Odoo is ready at ${odoo_url}."
    exit 0
  fi
  sleep 1
done

echo "Odoo did not become ready within 30 seconds."
exit 1
