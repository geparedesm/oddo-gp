#!/usr/bin/env bash

set -euo pipefail

mkdir -p addons config postgresql odoo-web-data
docker compose up -d --build
