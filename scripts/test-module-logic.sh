#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

if [[ $# -ne 1 ]]; then
  echo "Usage: scripts/test-module-logic.sh <module_name>"
  exit 1
fi

module_name="$1"

set -a
source ./.env
set +a

docker compose exec -T odoo \
  odoo -c /etc/odoo/odoo.conf \
  -d "${ODOO_DB_NAME}" \
  -u "${module_name}" \
  --test-enable \
  --test-tags "/${module_name}" \
  --no-http \
  --stop-after-init

./scripts/dev-restart-odoo.sh
