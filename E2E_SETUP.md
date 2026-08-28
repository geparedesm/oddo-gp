# E2E Tests - Guía de Configuración y Uso

## 🔒 Principio de Seguridad

Los tests E2E ahora están **protegidos contra daños accidentales** en tu base de datos de desarrollo:

1. **Base de datos dedicada**: Los tests E2E solo pueden ejecutarse en una base de pruebas separada
2. **Flag de activación explícita**: Requiere `E2E_TESTS_ENABLED=true` en `.env.e2e`
3. **Validación en tiempo de ejecución**: Verificación en `playwright.config.mjs` y `run-e2e.sh`
4. **Limpieza obligatoria**: Todos los registros creados por E2E deben eliminarse al terminar cada ejecución, incluso si alguna prueba falla

## 📋 Configuración Inicial

### 1. Crear una base de datos dedicada para E2E tests

```bash
# Crear o resetear la base de datos e2e_test
./scripts/setup-e2e-database.sh
# O especificar un nombre personalizado:
./scripts/setup-e2e-database.sh odoo16_commercial_property_e2e_custom
```

### 2. Actualizar `.env.e2e`

Abre el archivo `.env.e2e` y configura:

```bash
# Apunta a tu base de datos de PRUEBAS (no de desarrollo)
E2E_ODOO_DB=odoo16_commercial_property_e2e_test

# Cambiar a 'true' SOLO después de confirmar que usas la base de pruebas
E2E_TESTS_ENABLED=true
```

⚠️ **IMPORTANTE**: Nunca configures `E2E_TESTS_ENABLED=true` si `E2E_ODOO_DB` apunta a tu base de desarrollo.

### 3. Verificar la configuración

```bash
echo "E2E_TESTS_ENABLED=$(grep E2E_TESTS_ENABLED .env.e2e)"
echo "E2E_ODOO_DB=$(grep E2E_ODOO_DB .env.e2e)"
```

## 🧪 Ejecutar los E2E Tests

```bash
# Ejecutar todos los tests
./scripts/run-e2e.sh

# Ejecutar un test específico
./scripts/run-e2e.sh tests/e2e/odoo-login.spec.mjs

# Ejecutar con opciones de Playwright
./scripts/run-e2e.sh --headed  # Ver el navegador
./scripts/run-e2e.sh --debug   # Modo debug
```

### Mensajes de Error Esperados

Si ves estos errores, es **normal** - es la protección funcionando:

```
ERROR: E2E tests are disabled or pointing to a developer database for safety.
ERROR: E2E tests cannot run on a developer database!
```

**Solución**: Activa E2E en `.env.e2e` apuntando a la base de pruebas.

## 🧹 Limpiar Registros de E2E en Base de Desarrollo

Si de todas formas se crearon registros de E2E en tu base de desarrollo:

```bash
./scripts/cleanup-e2e-records.sh
```

Este script automáticamente:
- ✅ Detecta registros con patrón "E2E ", "e2e_", "test_", etc.
- ✅ Elimina usuarios, propiedades, arrendamientos, leads, visitas, etc.
- ✅ Genera un resumen de lo eliminado
- ✅ Solo se ejecuta en la base de desarrollo (desde `.env`)

**Dry-run** (ver qué se eliminaría sin eliminar):
```bash
# Ver el script para entender qué busca
cat scripts/cleanup-e2e-records.sh | grep -A 5 "is_e2e_record"
```

## 📊 Flujo de trabajo típico

### Semana de desarrollo normal:
```bash
# Tu base de desarrollo está protegida
./scripts/run-e2e.sh  # ❌ Falla: E2E_TESTS_ENABLED=false (protección activa)
```

### Cuando necesitas testear:
```bash
# 1. Configurar base de pruebas
./scripts/setup-e2e-database.sh

# 2. Habilitar en .env.e2e
# E2E_TESTS_ENABLED=true

# 3. Ejecutar tests
./scripts/run-e2e.sh

# 4. Limpiar datos de E2E después (OBLIGATORIO, también si fallan las pruebas)
./scripts/cleanup-e2e-records.sh
```

La limpieza debe ejecutarse siempre al finalizar la suite y debe abarcar todos
los modelos tocados por E2E, incluidos módulos auxiliares como `job_hunter`.
No se debe considerar completada una ejecución mientras existan registros
creados por las pruebas. Si el runner se automatiza, la limpieza debe estar en
un bloque `finally` o un `trap` para cubrir ejecuciones con error o
interrupción.

## 🔍 Verificación Técnica

### Verificaciones de seguridad en `playwright.config.mjs`:
```javascript
- E2E_TESTS_ENABLED === "true" ✓
- E2E_ODOO_DB no contiene "dev" O contiene "e2e" ✓
```

### Verificaciones en `run-e2e.sh`:
```bash
- E2E_TESTS_ENABLED=true ✓
- E2E_ODOO_DB no es una base de desarrollo ✓
```

### Patrones detectados en `cleanup-e2e-records.sh`:
```python
- Nombres: "E2E ", "e2e_", "e2e-", "test ", "test_", "test-"
- Logins: "e2e.", "e2e_", "property.user.e2e", ".test", "_test"
```

## 🚀 Mejores Prácticas

### ✅ HACER:
- Usar una base de datos separada para E2E tests
- Mantener `E2E_TESTS_ENABLED=false` por defecto
- Revisar los cambios en `.env.e2e` antes de ejecutar tests
- Limpiar registros de E2E después de testing extenso

### ❌ NO HACER:
- Apuntar `E2E_ODOO_DB` a tu base de desarrollo
- Dejar `E2E_TESTS_ENABLED=true` habilitado permanentemente
- Ignorar advertencias sobre bases de datos de desarrollo
- Hacer commit de cambios a `E2E_TESTS_ENABLED=true` si es innecesario

## 🆘 Troubleshooting

### "E2E tests are disabled"
**Causa**: `E2E_TESTS_ENABLED=false` en `.env.e2e`  
**Solución**: Cambia a `true` después de verificar que `E2E_ODOO_DB` apunta a base de pruebas

### "E2E tests cannot run on a developer database"
**Causa**: `E2E_ODOO_DB` contiene "dev" pero no "e2e"  
**Solución**: Usa `./scripts/setup-e2e-database.sh` para crear una base de pruebas

### "Unable to resolve E2E action IDs"
**Causa**: El módulo `commercial_property_management` no está instalado en la base de pruebas  
**Solución**: Ejecuta `./scripts/setup-e2e-database.sh` primero

### Base de datos no existe
**Causa**: `E2E_ODOO_DB` apunta a una base que no existe  
**Solución**: 
```bash
# Crear la base de datos
./scripts/setup-e2e-database.sh [db_name]

# O crear manualmente:
createdb -h localhost -U odoo odoo16_commercial_property_e2e_test
```

## 📚 Archivos Relacionados

- `.env.e2e` - Configuración de E2E (incluido E2E_TESTS_ENABLED)
- `.env.e2e.example` - Plantilla de configuración
- `playwright.config.mjs` - Config de Playwright con validaciones de seguridad
- `scripts/run-e2e.sh` - Script ejecutor con verificaciones
- `scripts/cleanup-e2e-records.sh` - Script de limpieza
- `scripts/setup-e2e-database.sh` - Script para crear base de pruebas
- `scripts/prepare-e2e-user.sh` - Preparación de usuario E2E (sin cambios)
- `tests/e2e/` - Tus tests de Playwright

## 📝 Notas de Versión

**v1.0** (2026-08-24):
- ✅ Agregado E2E_TESTS_ENABLED flag
- ✅ Validación de base de datos en playwright.config.mjs
- ✅ Script de limpieza automático (cleanup-e2e-records.sh)
- ✅ Script de setup de base de pruebas (setup-e2e-database.sh)
- ✅ Verificaciones en run-e2e.sh
