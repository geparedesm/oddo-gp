#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

set -a
source "${project_root}/.env"
set +a

if [[ -z "${HERMES_API_TOKEN:-}" || -z "${HERMES_MCP_CHANNEL_TOKEN:-}" ]]; then
  token_output="$(
    docker compose -f "${project_root}/docker-compose.yml" exec -T odoo \
      odoo shell -c /etc/odoo/odoo.conf -d "${ODOO_DB_NAME}" --no-http <<'PYTHON'
parameters = env["ir.config_parameter"].sudo()
api_token = parameters.get_param("commercial_property_management.hermes_api_token")
mcp_channel_token = parameters.get_param("commercial_property_management.hermes_mcp_channel_token")
if api_token:
    print(f"HERMES_API_TOKEN={api_token}")
if mcp_channel_token:
    print(f"HERMES_MCP_CHANNEL_TOKEN={mcp_channel_token}")
PYTHON
  )"
  while IFS= read -r line; do
    case "${line}" in
      HERMES_API_TOKEN=*)
        if [[ -z "${HERMES_API_TOKEN:-}" ]]; then
          export HERMES_API_TOKEN="${line#*=}"
        fi
        ;;
      HERMES_MCP_CHANNEL_TOKEN=*)
        if [[ -z "${HERMES_MCP_CHANNEL_TOKEN:-}" ]]; then
          export HERMES_MCP_CHANNEL_TOKEN="${line#*=}"
        fi
        ;;
    esac
  done <<< "${token_output}"
fi

: "${HERMES_API_TOKEN:?HERMES_API_TOKEN must be configured}"
: "${HERMES_MCP_CHANNEL_TOKEN:?HERMES_MCP_CHANNEL_TOKEN must be configured}"

exec node "${project_root}/tools/hermes-property-mcp.mjs"
