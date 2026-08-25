# Scripts - Referencia Rápida

## E2E Tests & Quality Assurance

### 🧪 Ejecutar E2E Tests
```bash
./run-e2e.sh [opciones]
```

**Opciones**:
- Sin argumentos: ejecuta todos los tests
- `tests/e2e/archivo.spec.mjs`: ejecuta un archivo específico
- `--headed`: muestra el navegador durante la ejecución
- `--debug`: modo debug interactivo

**Requisitos**:
- `E2E_TESTS_ENABLED=true` en `.env.e2e`
- `E2E_ODOO_DB` debe apuntar a base de pruebas (con "e2e" o "test" en nombre)

**Protección**: Si intentas ejecutar con base de desarrollo, el script falla automáticamente.

---

### 🧹 Limpiar Registros de E2E
```bash
./cleanup-e2e-records.sh
```

**Qué hace**:
- Detecta registros creados por E2E tests (patrones: "E2E ", "e2e_", "test_", etc.)
- Elimina de: usuarios, propiedades, unidades, partners, leases, leads, visitas, etc.
- Muestra resumen de registros eliminados
- Solo afecta la base de desarrollo (desde `.env`)

**Cuándo usar**:
- Después de ejecutar E2E tests que crearon datos no deseados
- Para mantener limpia la base de desarrollo

**Nota**: Script interactivo con confirmación

---

### 🔧 Crear Base de Datos E2E
```bash
./setup-e2e-database.sh [nombre_opcional]
```

**Ejemplos**:
```bash
./setup-e2e-database.sh                              # Crea: odoo16_commercial_property_e2e_test
./setup-e2e-database.sh odoo16_e2e_custom           # Crea: odoo16_e2e_custom
```

**Qué hace**:
1. Verifica que el nombre contenga "e2e" o "test"
2. Crea la base de datos PostgreSQL
3. Instala módulo commercial_property_management
4. Genera instrucciones para activar E2E

---

## 🔒 Sistema de Protección E2E

### Por Qué Existe:
Prevenir ejecución accidental de tests E2E en base de desarrollo y destrucción de datos.

### Cómo Funciona:
1. **playwright.config.mjs** - Verifica E2E_TESTS_ENABLED=true y BD no es dev
2. **run-e2e.sh** - Verifica flag y rechaza bases con "dev" en nombre
3. **cleanup-e2e-records.sh** - Limpia datos si algo se creó por error

### Flujo Seguro:
```
1. Por defecto: E2E_TESTS_ENABLED=false ✓ (protegido)
2. Para testear: 
   - Crear BD e2e: ./setup-e2e-database.sh
   - Habilitar: E2E_TESTS_ENABLED=true en .env.e2e
   - Ejecutar: ./run-e2e.sh
3. Después: Deshabilitar E2E_TESTS_ENABLED=false en .env.e2e
```

---

## 📊 Otros Scripts

- `prepare-e2e-user.sh` - Prepara usuario de E2E (llamado automáticamente)
- `dev-update-module.sh <module>` - Actualizar módulo específico
- `dev-shell.sh` - Shell de Odoo para debugging

---

## 🎯 Checklist Rápido

**Antes de ejecutar E2E tests:**
- [ ] ¿Tengo una base de pruebas separada?
- [ ] ¿Mi BD de pruebas tiene "e2e" o "test" en el nombre?
- [ ] ¿He configurado E2E_TESTS_ENABLED=true en .env.e2e?
- [ ] ¿Mi E2E_ODOO_DB apunta a la base de pruebas (NO desarrollo)?

**Después de ejecutar E2E tests:**
- [ ] ¿He deshabiltiado E2E_TESTS_ENABLED=false?
- [ ] ¿He limpiado registros con ./cleanup-e2e-records.sh si es necesario?

---

## 📚 Documentación Completa

Ver: `../E2E_SETUP.md`

Temas cubiertos:
- Configuración inicial
- Mensajes de error y soluciones
- Mejores prácticas
- Flujos de trabajo
- Troubleshooting
