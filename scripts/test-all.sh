#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

module_name="${1:-commercial_property_management}"

./scripts/test-module-install.sh "${module_name}"
./scripts/dev-update-module.sh "${module_name}"
npm run test:e2e
