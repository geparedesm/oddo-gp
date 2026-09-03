#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

set -a
source ./.env
source ./.env.e2e
set +a

runtime_env_file=".env.e2e.runtime"

for required_variable in E2E_ODOO_DB E2E_ODOO_USERNAME E2E_PROPERTY_USER E2E_PROPERTY_USER_PASSWORD; do
  if [[ -z "${!required_variable:-}" || "${!required_variable}" == replace-with-* ]]; then
    echo "${required_variable} must be set in .env.e2e."
    exit 1
  fi
done

export E2E_ODOO_USERNAME E2E_PROPERTY_USER E2E_PROPERTY_USER_PASSWORD

docker compose exec -T \
  -e E2E_PROPERTY_USER \
  -e E2E_PROPERTY_USER_PASSWORD \
  -e E2E_ODOO_USERNAME \
  odoo odoo shell -c /etc/odoo/odoo.conf -d "${E2E_ODOO_DB}" --no-http <<'PYTHON'
import os

login = os.environ["E2E_PROPERTY_USER"]
password = os.environ["E2E_PROPERTY_USER_PASSWORD"]
property_user_group = env.ref("commercial_property_management.group_property_user")
e2e_cleanup_group = env.ref("job_hunter_management.group_job_hunter_e2e_cleanup")
internal_user_group = env.ref("base.group_user")

user = env["res.users"].sudo().search([("login", "=", login)], limit=1)
values = {
    "name": "E2E Property User",
    "login": login,
    "email": f"{login}@example.test",
    "password": password,
    "company_id": env.company.id,
    "company_ids": [(6, 0, env.company.ids)],
    "groups_id": [(6, 0, [internal_user_group.id, property_user_group.id, e2e_cleanup_group.id])],
}

if user:
    user.write(values)
else:
    env["res.users"].sudo().create(values)

login_user = env["res.users"].sudo().search(
    [("login", "=", os.environ["E2E_ODOO_USERNAME"])], limit=1,
)
if login_user and login_user.id != user.id:
    login_user.write({
        "groups_id": [(4, internal_user_group.id), (4, property_user_group.id), (4, e2e_cleanup_group.id)],
    })

env.cr.commit()
PYTHON

action_ids="$(
  docker compose exec -T odoo odoo shell -c /etc/odoo/odoo.conf -d "${E2E_ODOO_DB}" --no-http <<'PYTHON'
print(f"E2E_UNIT_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_unit').id}")
print(f"E2E_TENANT_ACTION_ID={env.ref('commercial_property_management.action_commercial_tenant').id}")
print(f"E2E_LEASE_ACTION_ID={env.ref('commercial_property_management.action_commercial_lease').id}")
print(f"E2E_LEASE_DASHBOARD_ACTION_ID={env.ref('commercial_property_management.action_commercial_lease_operations_dashboard').id}")
print(f"E2E_ENQUIRY_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_lead').id}")
print(f"E2E_VISIT_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_visit').id}")
print(f"E2E_RESERVATION_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_reservation').id}")
print(f"E2E_WHATSAPP_POLICY_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_settings').id}")
print(f"E2E_APPLICATION_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_application').id}")
print(f"E2E_INTEGRATION_ALERT_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_integration_alert').id}")
print(f"E2E_MAINTENANCE_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_maintenance').id}")
print(f"E2E_MAINTENANCE_DASHBOARD_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_maintenance_dashboard').id}")
print(f"E2E_HANDOVER_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_handover').id}")
print(f"E2E_PENALTY_ACTION_ID={env.ref('commercial_property_management.action_commercial_lease_penalty').id}")
print(f"E2E_PORTFOLIO_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_portfolio').id}")
print(f"E2E_DISTRIBUTION_CHANNEL_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_distribution_channel').id}")
print(f"E2E_CAMPAIGN_ATTRIBUTION_ACTION_ID={env.ref('commercial_property_management.action_commercial_property_campaign_attribution').id}")
PYTHON
)"

unit_action_id=""
tenant_action_id=""
lease_action_id=""
lease_dashboard_action_id=""
enquiry_action_id=""
visit_action_id=""
reservation_action_id=""
whatsapp_policy_action_id=""
application_action_id=""
integration_alert_action_id=""
maintenance_action_id=""
maintenance_dashboard_action_id=""
handover_action_id=""
penalty_action_id=""
portfolio_action_id=""
distribution_channel_action_id=""
campaign_attribution_action_id=""
while IFS= read -r line; do
  case "${line}" in
    E2E_UNIT_ACTION_ID=*) unit_action_id="${line#*=}" ;;
    E2E_TENANT_ACTION_ID=*) tenant_action_id="${line#*=}" ;;
    E2E_LEASE_ACTION_ID=*) lease_action_id="${line#*=}" ;;
    E2E_LEASE_DASHBOARD_ACTION_ID=*) lease_dashboard_action_id="${line#*=}" ;;
    E2E_ENQUIRY_ACTION_ID=*) enquiry_action_id="${line#*=}" ;;
    E2E_VISIT_ACTION_ID=*) visit_action_id="${line#*=}" ;;
    E2E_RESERVATION_ACTION_ID=*) reservation_action_id="${line#*=}" ;;
    E2E_WHATSAPP_POLICY_ACTION_ID=*) whatsapp_policy_action_id="${line#*=}" ;;
    E2E_APPLICATION_ACTION_ID=*) application_action_id="${line#*=}" ;;
    E2E_INTEGRATION_ALERT_ACTION_ID=*) integration_alert_action_id="${line#*=}" ;;
    E2E_MAINTENANCE_ACTION_ID=*) maintenance_action_id="${line#*=}" ;;
    E2E_MAINTENANCE_DASHBOARD_ACTION_ID=*) maintenance_dashboard_action_id="${line#*=}" ;;
    E2E_HANDOVER_ACTION_ID=*) handover_action_id="${line#*=}" ;;
    E2E_PENALTY_ACTION_ID=*) penalty_action_id="${line#*=}" ;;
    E2E_PORTFOLIO_ACTION_ID=*) portfolio_action_id="${line#*=}" ;;
    E2E_DISTRIBUTION_CHANNEL_ACTION_ID=*) distribution_channel_action_id="${line#*=}" ;;
    E2E_CAMPAIGN_ATTRIBUTION_ACTION_ID=*) campaign_attribution_action_id="${line#*=}" ;;
  esac
done <<< "${action_ids}"

if [[ -z "${unit_action_id}" || -z "${tenant_action_id}" || -z "${lease_action_id}" || -z "${lease_dashboard_action_id}" || -z "${enquiry_action_id}" || -z "${visit_action_id}" || -z "${reservation_action_id}" || -z "${whatsapp_policy_action_id}" || -z "${application_action_id}" || -z "${integration_alert_action_id}" || -z "${maintenance_action_id}" || -z "${maintenance_dashboard_action_id}" || -z "${handover_action_id}" || -z "${penalty_action_id}" || -z "${portfolio_action_id}" || -z "${distribution_channel_action_id}" || -z "${campaign_attribution_action_id}" ]]; then
  echo "Unable to resolve E2E action IDs from Odoo XML IDs."
  exit 1
fi

printf 'E2E_UNIT_ACTION_ID=%s\nE2E_TENANT_ACTION_ID=%s\nE2E_LEASE_ACTION_ID=%s\nE2E_LEASE_DASHBOARD_ACTION_ID=%s\nE2E_ENQUIRY_ACTION_ID=%s\nE2E_VISIT_ACTION_ID=%s\nE2E_RESERVATION_ACTION_ID=%s\nE2E_WHATSAPP_POLICY_ACTION_ID=%s\nE2E_APPLICATION_ACTION_ID=%s\nE2E_INTEGRATION_ALERT_ACTION_ID=%s\nE2E_MAINTENANCE_ACTION_ID=%s\nE2E_MAINTENANCE_DASHBOARD_ACTION_ID=%s\nE2E_HANDOVER_ACTION_ID=%s\nE2E_PENALTY_ACTION_ID=%s\nE2E_PORTFOLIO_ACTION_ID=%s\nE2E_DISTRIBUTION_CHANNEL_ACTION_ID=%s\nE2E_CAMPAIGN_ATTRIBUTION_ACTION_ID=%s\n' \
  "${unit_action_id}" "${tenant_action_id}" "${lease_action_id}" "${lease_dashboard_action_id}" "${enquiry_action_id}" "${visit_action_id}" "${reservation_action_id}" "${whatsapp_policy_action_id}" "${application_action_id}" "${integration_alert_action_id}" "${maintenance_action_id}" "${maintenance_dashboard_action_id}" "${handover_action_id}" "${penalty_action_id}" "${portfolio_action_id}" "${distribution_channel_action_id}" "${campaign_attribution_action_id}" > "${runtime_env_file}"

echo "E2E Property User is ready."
