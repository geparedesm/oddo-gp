#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

./scripts/prepare-e2e-user.sh
set -a
source ./.env.e2e.runtime
set +a
npx playwright test "$@"
