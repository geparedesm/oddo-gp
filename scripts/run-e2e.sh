#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

# Verificación de seguridad: asegurar que E2E tests está habilitado explícitamente
set -a
source ./.env.e2e
set +a

if [[ "${E2E_TESTS_ENABLED:-false}" != "true" ]]; then
  echo "❌ ERROR: E2E tests are disabled for safety."
  echo ""
  echo "Your configuration:"
  echo "  E2E_TESTS_ENABLED: ${E2E_TESTS_ENABLED:-false}"
  echo "  E2E_ODOO_DB: ${E2E_ODOO_DB}"
  echo ""
  echo "To enable E2E tests:"
  echo "1. Ensure E2E_ODOO_DB points to a TEST database (not your dev database)"
  echo "2. Set E2E_TESTS_ENABLED=true in .env.e2e"
  echo "3. Run this script again"
  echo ""
  exit 1
fi

# Verificación adicional: rechazar bases de datos de desarrollo
if [[ "${E2E_ODOO_DB}" == *"dev"* ]] && [[ "${E2E_ODOO_DB}" != *"e2e"* ]]; then
  echo "❌ ERROR: E2E tests cannot run on a developer database!"
  echo ""
  echo "Database detected: ${E2E_ODOO_DB}"
  echo ""
  echo "To protect your development data:"
  echo "1. Create or use a separate test database (e.g., odoo16_commercial_property_e2e_test)"
  echo "2. Update E2E_ODOO_DB in .env.e2e to point to the test database"
  echo "3. Set E2E_TESTS_ENABLED=true only after confirming the test database"
  echo ""
  exit 1
fi

./scripts/prepare-e2e-user.sh
set -a
source ./.env.e2e.runtime
set +a
npx playwright test "$@"
