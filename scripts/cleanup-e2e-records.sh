#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${project_root}"

set -a
source ./.env
set +a

TARGET_DB="${ODOO_DB_NAME:-odoo16_commercial_property_dev}"

echo "🧹 Limpiando registros creados por E2E tests de: ${TARGET_DB}"
echo ""

# Configurar colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Crear archivo temporal para el script Python
cleanup_script=$(mktemp)
trap "rm -f $cleanup_script" EXIT

# Escribir el script de limpieza Python
cat > "$cleanup_script" << 'PYTHON'
import re

# Patrón para detectar registros creados por E2E tests
# Criterios:
# 1. Nombre/login contiene "E2E", "e2e" o "E2E Test"
# 2. Nombre contiene prefijo "E2E " que típicamente indica test data
# 3. Login contiene patrones de test: "e2e.", "test."

def is_e2e_record(record_name, record_login=None):
    """Detectar si un registro fue creado por E2E tests."""
    name_lower = (record_name or "").lower()
    
    # Criterios de nombre
    e2e_patterns = [
        "e2e ",
        "e2e_",
        "e2e-",
        "test ",
        "test_",
        "test-",
    ]
    
    if any(pattern in name_lower for pattern in e2e_patterns):
        return True
    
    # Criterios de login (para usuarios)
    if record_login:
        login_lower = record_login.lower()
        login_patterns = [
            "e2e.",
            "e2e_",
            "property.user.e2e",
            ".test",
            "_test",
        ]
        if any(pattern in login_lower for pattern in login_patterns):
            return True
    
    return False

# Counters
total_deleted = 0
deleted_by_model = {}

# 1. Limpiar usuarios de E2E
print("Limpiando usuarios E2E...")
users = env["res.users"].search([], order="id")
for user in users:
    if is_e2e_record(user.name, user.login):
        print(f"  ❌ Eliminando usuario: {user.login} ({user.name})")
        user.unlink()
        total_deleted += 1
        deleted_by_model["res.users"] = deleted_by_model.get("res.users", 0) + 1

# 2. Limpiar propiedades comerciales
print("Limpiando propiedades comerciales E2E...")
properties = env["commercial.property"].search([], order="id")
for prop in properties:
    if is_e2e_record(prop.name):
        print(f"  ❌ Eliminando propiedad: {prop.name}")
        prop.unlink()
        total_deleted += 1
        deleted_by_model["commercial.property"] = deleted_by_model.get("commercial.property", 0) + 1

# 3. Limpiar unidades de propiedades
print("Limpiando unidades de propiedades E2E...")
units = env["commercial.property.unit"].search([], order="id")
for unit in units:
    if is_e2e_record(unit.name):
        print(f"  ❌ Eliminando unidad: {unit.name}")
        unit.unlink()
        total_deleted += 1
        deleted_by_model["commercial.property.unit"] = deleted_by_model.get("commercial.property.unit", 0) + 1

# 4. Limpiar partners/tenantes
print("Limpiando partners/tenantes E2E...")
partners = env["res.partner"].search([("is_company", "=", False)], order="id")
for partner in partners:
    if is_e2e_record(partner.name):
        print(f"  ❌ Eliminando partner: {partner.name}")
        partner.unlink()
        total_deleted += 1
        deleted_by_model["res.partner"] = deleted_by_model.get("res.partner", 0) + 1

# 5. Limpiar leases
print("Limpiando arrendamientos E2E...")
leases = env["commercial.lease"].search([], order="id")
for lease in leases:
    # Buscar si la propiedad o el arrendatario tiene "E2E" en el nombre
    if (is_e2e_record(lease.property_id.name) or 
        is_e2e_record(lease.tenant_id.name)):
        print(f"  ❌ Eliminando arrendamiento: {lease.name}")
        lease.unlink()
        total_deleted += 1
        deleted_by_model["commercial.lease"] = deleted_by_model.get("commercial.lease", 0) + 1

# 6. Limpiar leads/enquiries
print("Limpiando leads/enquiries E2E...")
leads = env["commercial.property.lead"].search([], order="id")
for lead in leads:
    if is_e2e_record(lead.name, lead.email or ""):
        print(f"  ❌ Eliminando lead: {lead.name}")
        lead.unlink()
        total_deleted += 1
        deleted_by_model["commercial.property.lead"] = deleted_by_model.get("commercial.property.lead", 0) + 1

# 7. Limpiar visits
print("Limpiando visitas E2E...")
visits = env["commercial.property.visit"].search([], order="id")
for visit in visits:
    if is_e2e_record(visit.property_id.name):
        print(f"  ❌ Eliminando visita: {visit.name}")
        visit.unlink()
        total_deleted += 1
        deleted_by_model["commercial.property.visit"] = deleted_by_model.get("commercial.property.visit", 0) + 1

# 8. Limpiar reservaciones
print("Limpiando reservaciones E2E...")
reservations = env["commercial.property.reservation"].search([], order="id")
for reservation in reservations:
    if is_e2e_record(reservation.property_id.name):
        print(f"  ❌ Eliminando reservación: {reservation.name}")
        reservation.unlink()
        total_deleted += 1
        deleted_by_model["commercial.property.reservation"] = deleted_by_model.get("commercial.property.reservation", 0) + 1

# 9. Limpiar aplicaciones
print("Limpiando aplicaciones E2E...")
applications = env["commercial.property.application"].search([], order="id")
for application in applications:
    if is_e2e_record(application.name):
        print(f"  ❌ Eliminando aplicación: {application.name}")
        application.unlink()
        total_deleted += 1
        deleted_by_model["commercial.property.application"] = deleted_by_model.get("commercial.property.application", 0) + 1

# 10. Limpiar mantenimientos
print("Limpiando mantenimientos E2E...")
maintenance = env["commercial.property.maintenance"].search([], order="id")
for item in maintenance:
    if is_e2e_record(item.property_id.name):
        print(f"  ❌ Eliminando mantenimiento: {item.name}")
        item.unlink()
        total_deleted += 1
        deleted_by_model["commercial.property.maintenance"] = deleted_by_model.get("commercial.property.maintenance", 0) + 1

# 11. Limpiar handovers
print("Limpiando handovers E2E...")
handovers = env["commercial.property.handover"].search([], order="id")
for handover in handovers:
    if is_e2e_record(handover.property_id.name):
        print(f"  ❌ Eliminando handover: {handover.name}")
        handover.unlink()
        total_deleted += 1
        deleted_by_model["commercial.property.handover"] = deleted_by_model.get("commercial.property.handover", 0) + 1

# Commit final
env.cr.commit()

# Resumen
print("")
print("=" * 60)
print("RESUMEN DE LIMPIEZA")
print("=" * 60)
if total_deleted == 0:
    print("✅ No se encontraron registros de E2E tests")
else:
    print(f"✅ Total de registros eliminados: {total_deleted}")
    print("")
    print("Detalles por modelo:")
    for model, count in sorted(deleted_by_model.items()):
        print(f"  • {model}: {count}")
PYTHON

echo "Ejecutando limpieza en Odoo..."
echo ""

docker compose exec -T odoo odoo shell -c /etc/odoo/odoo.conf -d "${TARGET_DB}" --no-http < "$cleanup_script"

echo ""
echo "✅ Limpieza completada"
