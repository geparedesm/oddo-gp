#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

set -a
source "${project_root}/.env"
set +a

if [[ -z "${HERMES_API_TOKEN:-}" ]]; then
  token_output="$(
    docker compose -f "${project_root}/docker-compose.yml" exec -T odoo \
      odoo shell -c /etc/odoo/odoo.conf -d "${ODOO_DB_NAME}" --no-http <<'PYTHON'
token = env["ir.config_parameter"].sudo().get_param("commercial_property_management.hermes_api_token")
if token:
    print(f"HERMES_API_TOKEN={token}")
PYTHON
  )"
  while IFS= read -r line; do
    case "${line}" in
      HERMES_API_TOKEN=*) export HERMES_API_TOKEN="${line#*=}" ;;
    esac
  done <<< "${token_output}"
fi

exec node "${project_root}/tools/hermes-property-mcp.mjs"