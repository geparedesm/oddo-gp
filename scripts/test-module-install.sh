#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

if [[ $# -ne 1 ]]; then
  echo "Usage: scripts/test-module-install.sh <module_name>"
  exit 1
fi

module_name="$1"

if [[ ! "${module_name}" =~ ^[a-z][a-z0-9_]*$ ]]; then
  echo "Module names must contain lowercase letters, numbers, and underscores only."
  exit 1
fi

set -a
source ./.env
set +a

test_db_name="${ODOO_MODULE_TEST_DB_NAME:-${ODOO_DB_NAME}_install_test}"

if [[ ! "${test_db_name}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "ODOO_MODULE_TEST_DB_NAME must be a valid PostgreSQL identifier."
  exit 1
fi

if [[ "${test_db_name}" == "${ODOO_DB_NAME}" ]]; then
  echo "The installation test database must differ from ODOO_DB_NAME."
  exit 1
fi

drop_test_database() {
  docker compose exec -T db \
    dropdb -U "${POSTGRES_USER}" --if-exists --force "${test_db_name}"
}

cleanup() {
  local exit_code=$?

  if [[ "${exit_code}" -eq 0 && "${KEEP_TEST_DB:-0}" != "1" ]]; then
    echo "Removing temporary database ${test_db_name}."
    drop_test_database
  elif [[ "${exit_code}" -ne 0 ]]; then
    echo "Installation test failed. Database preserved for diagnosis: ${test_db_name}."
  else
    echo "Temporary database preserved: ${test_db_name}."
  fi

  exit "${exit_code}"
}

trap cleanup EXIT

echo "Recreating isolated installation test database: ${test_db_name}."
drop_test_database
docker compose exec -T db \
  createdb -U "${POSTGRES_USER}" "${test_db_name}"

echo "Installing ${module_name} from scratch."
docker compose exec -T odoo \
  odoo -c /etc/odoo/odoo.conf \
  -d "${test_db_name}" \
  -i "${module_name}" \
  --without-demo=all \
  --stop-after-init

module_state="$(docker compose exec -T db \
  psql -U "${POSTGRES_USER}" -d "${test_db_name}" -tAc \
  "SELECT state FROM ir_module_module WHERE name = '${module_name}'")"

if [[ "${module_state}" != "installed" ]]; then
  echo "Expected ${module_name} to be installed, found: ${module_state:-missing}."
  exit 1
fi

echo "Fresh installation verified: ${module_name} is installed in ${test_db_name}."
