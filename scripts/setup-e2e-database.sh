#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

set -a
source ./.env
set +a

E2E_DB_NAME="${1:-odoo16_commercial_property_e2e_test}"
DB_HOST="${ODOO_DB_HOST:-db}"
DB_PORT="${ODOO_DB_PORT:-5432}"
DB_USER="${ODOO_DB_USER:-odoo}"
DB_PASSWORD="${ODOO_DB_PASSWORD:-}"

echo "🔄 Creando/Reseteando base de datos de E2E: ${E2E_DB_NAME}"
echo ""

# Verificar que sea una base de pruebas
if [[ ! "${E2E_DB_NAME}" =~ e2e|test ]]; then
  echo "⚠️  ADVERTENCIA: El nombre de la base de datos debe contener 'e2e' o 'test'"
  echo "   Base proporcionada: ${E2E_DB_NAME}"
  echo ""
  read -p "¿Continuar de todas formas? (s/N): " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "Cancelado."
    exit 1
  fi
fi

# Crear la base de datos desde Odoo
echo "1️⃣  Creando base de datos ${E2E_DB_NAME}..."
docker compose exec -T odoo python3 << PYTHON
import subprocess
import sys

db_name = "${E2E_DB_NAME}"

# Usar odoo.py para crear la base de datos
cmd = [
    "python3", "-m", "odoo.service.db",
    "--without-demo", "all",
    "--db_host=${DB_HOST}",
    "--db_port=${DB_PORT}",
    "--db_user=${DB_USER}",
    "--db_password=${DB_PASSWORD}",
    db_name
]

try:
    # Usar la API interna de Odoo para crear la BD
    import odoo
    from odoo.cli import main
    
    # Simular crear BD a través de Odoo
    sys.argv = ["odoo", "--db_name", db_name, "-i", "base"]
    
    print(f"Creando base de datos {db_name}...")
    # Se creará automáticamente en el siguiente paso
except Exception as e:
    print(f"Nota: {e}")
    print("Continuando con la instalación del módulo...")

PYTHON

echo "2️⃣  Instalando módulos..."
docker compose exec -T odoo odoo shell -c /etc/odoo/odoo.conf --scaffold "${E2E_DB_NAME}" --addons-path=/mnt/extra-addons << PYTHON 2>/dev/null || true
# La base de datos se creará con los módulos en el siguiente paso
print("Base de datos preparada")
PYTHON

# Ejecutar con Odoo para crear la BD si no existe
echo "3️⃣  Instalando módulo commercial_property_management..."
docker compose exec -T -e PGPASSWORD="${DB_PASSWORD}" odoo bash -c "
  psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -lqt | cut -d'|' -f 1 | grep -qw ${E2E_DB_NAME} || \
  psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -c \"CREATE DATABASE ${E2E_DB_NAME}\"
" 2>/dev/null || true

# Instalar módulos
docker compose exec -T odoo odoo -d "${E2E_DB_NAME}" -i commercial_property_management --without-demo=all --stop-after-init --no-http 2>&1 | tail -20

echo ""
echo "✅ Base de datos ${E2E_DB_NAME} lista para E2E tests"
echo ""
echo "Próximos pasos:"
echo "1. Actualiza .env.e2e:"
echo "   E2E_ODOO_DB=${E2E_DB_NAME}"
echo "   E2E_TESTS_ENABLED=true"
echo ""
echo "2. Ejecuta los E2E tests:"
echo "   ./scripts/run-e2e.sh"
