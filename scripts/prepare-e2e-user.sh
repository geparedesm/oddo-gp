#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

set -a
source ./.env
source ./.env.e2e
set +a

runtime_env_file=".env.e2e.runtime"

for required_variable in E2E_ODOO_DB E2E_PROPERTY_USER E2E_PROPERTY_USER_PASSWORD; do
  if [[ -z "${!required_variable:-}" || "${!required_variable}" == replace-with-* ]]; then
    echo "${required_variable} must be set in .env.e2e."
    exit 1
  fi
done

export E2E_PROPERTY_USER E2E_PROPERTY_USER_PASSWORD

docker compose exec -T \
  -e E2E_PROPERTY_USER \
  -e E2E_PROPERTY_USER_PASSWORD \
  odoo odoo shell -c /etc/odoo/odoo.conf -d "${E2E_ODOO_DB}" --no-http <<'PYTHON'
import os

login = os.environ["E2E_PROPERTY_USER"]
password = os.environ["E2E_PROPERTY_USER_PASSWORD"]
property_user_group = env.ref("commercial_property_management.group_property_user")
internal_user_group = env.ref("base.group_user")

user = env["res.users"].sudo().search([("login", "=", login)], limit=1)
values = {
    "name": "E2E Property User",
    "login": login,
    "email": f"{login}@example.test",
    "password": password,
    "company_id": env.company.id,
    "company_ids": [(6, 0, env.company.ids)],
    "groups_id": [(6, 0, [internal_user_group.id, property_user_group.id])],
}

if user:
    user.write(values)
else:
    env["res.users"].sudo().create(values)

env.cr.commit()
PYTHON

action_ids="$(
  docker compose exec -T odoo odoo shell -c /etc/odoo/odoo.conf -d "${E2E_ODOO_DB}" --no-http <<'PYTHON'
print(f"E2E_TENANT_ACTION_ID={env.ref('commercial_property_management.action_commercial_tenant').id}")
print(f"E2E_LEASE_ACTION_ID={env.ref('commercial_property_management.action_commercial_lease').id}")
print(f"E2E_LEASE_DASHBOARD_ACTION_ID={env.ref('commercial_property_management.action_commercial_lease_operations_dashboard').id}")
print(f"E2E_ENQUIRY_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_lead').id}")
PYTHON
)"

tenant_action_id=""
lease_action_id=""
lease_dashboard_action_id=""
enquiry_action_id=""
while IFS= read -r line; do
  case "${line}" in
    E2E_TENANT_ACTION_ID=*) tenant_action_id="${line#*=}" ;;
    E2E_LEASE_ACTION_ID=*) lease_action_id="${line#*=}" ;;
    E2E_LEASE_DASHBOARD_ACTION_ID=*) lease_dashboard_action_id="${line#*=}" ;;
    E2E_ENQUIRY_ACTION_ID=*) enquiry_action_id="${line#*=}" ;;
  esac
done <<< "${action_ids}"

if [[ -z "${tenant_action_id}" || -z "${lease_action_id}" || -z "${lease_dashboard_action_id}" || -z "${enquiry_action_id}" ]]; then
  echo "Unable to resolve E2E action IDs from Odoo XML IDs."
  exit 1
fi

printf 'E2E_TENANT_ACTION_ID=%s\nE2E_LEASE_ACTION_ID=%s\nE2E_LEASE_DASHBOARD_ACTION_ID=%s\nE2E_ENQUIRY_ACTION_ID=%s\n' \
  "${tenant_action_id}" "${lease_action_id}" "${lease_dashboard_action_id}" "${enquiry_action_id}" > "${runtime_env_file}"

echo "E2E Property User is ready."
