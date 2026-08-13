#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: scripts/dev-update-module.sh <module_name>"
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
  --stop-after-init
