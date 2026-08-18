# 📋 RESUMEN EJECUTIVO - Autenticación por Token para Control HE

## ✅ Implementado

### Backend (FastAPI)
```
✓ GET /he-control - Lee parámetro ?token=xxx
✓ Valida token contra tabla ni_he_tokens_revision
✓ Carga automáticamente: fecha_inicio, fecha_fin, departamento, supervisor
✓ Retorna error.html si token es inválido o expiró
✓ Todos POST routes (confirmar, rechazar, ajustar, manual) reciben y mantienen token
✓ Token se preserva en todos los redirects
✓ Registra último acceso (ultimo_acceso) en tabla de tokens
```

### Frontend (Jinja2 Templates)
```
✓ he_control.html - Token hidden en formularios de:
  - Filtros (GET)
  - Agregar HE manual
  - Confirmar evento
  - Rechazar evento
  - Ajustar HE
✓ error.html - Página amigable para ligas inválidas
✓ Token se mantiene en toda la sesión del supervisor
```

### Base de Datos

#### Tabla: ni_he_tokens_revision
```sql
id BIGINT PK              -- ID único
token VARCHAR(100)        -- Único, código seguro
fecha_inicio/fin DATE     -- Rango de datos a revisar
semana_piloto VARCHAR     -- 2026-06-24_2026-06-30
supervisor_numero VARCHAR -- ID del supervisor
supervisor_nombre VARCHAR -- Nombre del supervisor
supervisor_email VARCHAR  -- Email para notificaciones
gerente_numero VARCHAR    -- ID del gerente
gerente_nombre VARCHAR    -- Nombre del gerente
gerente_email VARCHAR     -- Email del gerente
departamento VARCHAR      -- ACABADO, ALMACEN, etc.
rol_acceso VARCHAR        -- SUPERVISOR, GERENTE, RH
activo BIT                -- 1=activo, 0=desactivado
fecha_expiracion DATETIME -- Cuándo expira el token
fecha_creacion DATETIME   -- Cuándo se creó (auto)
ultimo_acceso DATETIME    -- Cuándo accedió por última vez
```

#### Tabla: ni_he_notificaciones_revision
```sql
id BIGINT PK
token_id BIGINT           -- Referencia a token
fecha_inicio/fin DATE
semana_piloto VARCHAR
supervisor_numero VARCHAR
supervisor_nombre VARCHAR
supervisor_email VARCHAR
departamento VARCHAR
eventos_pendientes INT    -- Cantidad de HE por revisar
empleados INT             -- Cantidad de empleados
minutos_detectados INT    -- Total de minutos de HE
canal VARCHAR             -- EMAIL, WHATSAPP, SMS
destino VARCHAR           -- Teléfono o email
asunto NVARCHAR           -- Asunto del mensaje
mensaje NVARCHAR          -- Cuerpo del mensaje
estatus VARCHAR           -- PENDIENTE, ENVIADO, FALLIDO
fecha_creacion DATETIME
fecha_envio DATETIME
error_envio NVARCHAR      -- Log de error si aplica
```

### Procedimiento Almacenado

#### sp_ni_he_generar_tokens_revision
```sql
-- Genera automáticamente 1 token por supervisor/departamento/periodo
-- Solo para supervisores que tengan HE PENDIENTE
-- Evita duplicar tokens para el mismo supervisor en el mismo periodo

EXEC sp_ni_he_generar_tokens_revision
    @fecha_inicio = '2026-06-24',
    @fecha_fin = '2026-06-30',
    @semana_piloto = '2026-06-24_2026-06-30';
```

---

## 🚀 Cómo Activar el Piloto

### Paso 1: Crear Tablas y SP en BD (una sola vez)
```bash
# Ejecutar script SQL completo
sqlcmd -S SERVIDOR -d BD -i create_tokens.sql
```

**Output esperado**:
```
✓ Tabla ni_he_tokens_revision creada
✓ Tabla ni_he_notificaciones_revision creada
Tokens generados exitosamente
```

### Paso 2: Generar Tokens por Supervisor Automáticamente
```sql
-- Ejecutar SP que crea UN token por supervisor/departamento con HE pendiente
EXEC sp_ni_he_generar_tokens_revision
    @fecha_inicio = '2026-06-24',
    @fecha_fin = '2026-06-30',
    @semana_piloto = '2026-06-24_2026-06-30';

-- Ver resultados
SELECT TOP 10
    supervisor_nombre,
    supervisor_email,
    departamento,
    token,
    fecha_expiracion
FROM ni_he_tokens_revision
WHERE semana_piloto = '2026-06-24_2026-06-30'
  AND activo = 1;
```

**Output esperado**:
```
supervisor_nombre      departamento  eventos  empleados  horas  link_revision
VERONICA PEREZ         ACABADO       15       8          12.50  http://192.168.39.122:8009/he-control?token=abc123...
CARLOS RODRIGUEZ       ALMACEN       22       12         18.25  http://192.168.39.122:8009/he-control?token=def456...
```

### Paso 3: Enviar Notificaciones a Supervisores
```sql
-- Insertar notificaciones para enviar por email/WhatsApp
INSERT INTO ni_he_notificaciones_revision (
    token_id,
    fecha_inicio,
    fecha_fin,
    semana_piloto,
    supervisor_numero,
    supervisor_nombre,
    supervisor_email,
    departamento,
    eventos_pendientes,
    empleados,
    minutos_detectados,
    canal,
    destino,
    asunto,
    mensaje,
    estatus
)
SELECT
    t.id,
    t.fecha_inicio,
    t.fecha_fin,
    t.semana_piloto,
    t.supervisor_numero,
    t.supervisor_nombre,
    t.supervisor_email,
    t.departamento,
    COUNT(e.id),
    COUNT(DISTINCT e.numero_empleado),
    SUM(e.minutos_detectados),
    'EMAIL',
    t.supervisor_email,
    'Control HE en línea - Piloto Semana 24-30 junio',
    CONCAT('
        Buen día, ', t.supervisor_nombre, '.
        Se detectaron ', COUNT(e.id), ' horas extra pendientes de revisión 
        para su personal en ', t.departamento, '.
        
        Acceda al portal: http://192.168.39.122:8009/he-control?token=', t.token, '
        
        Expira: ', t.fecha_expiracion, '
    '),
    'PENDIENTE'
FROM ni_he_tokens_revision t
INNER JOIN ni_he_eventos_jornada e
    ON e.supervisor_numero = t.supervisor_numero
   AND e.departamento = t.departamento
   AND e.fecha_operativa BETWEEN t.fecha_inicio AND t.fecha_fin
   AND e.semana_piloto = t.semana_piloto
   AND e.estatus = 'PENDIENTE'
WHERE t.semana_piloto = '2026-06-24_2026-06-30'
  AND t.activo = 1
GROUP BY t.id, t.fecha_inicio, t.fecha_fin, t.semana_piloto,
         t.supervisor_numero, t.supervisor_nombre, t.supervisor_email,
         t.departamento, t.token, t.fecha_expiracion;
```

### Paso 4: Supervisor Accede a Panel
- Supervisor recibe correo con link: `http://192.168.39.122:8009/he-control?token=abc123`
- Hace clic
- Sistema valida token
- Panel carga automáticamente con su departamento y fechas
- Puede confirmar/rechazar/ajustar eventos

### Paso 5: Auditoría
```sql
-- Ver tokens en uso
SELECT
    supervisor_nombre,
    departamento,
    fecha_creacion,
    ultimo_acceso,
    fecha_expiracion,
    CASE WHEN activo = 1 THEN 'ACTIVO' ELSE 'EXPIRADO' END AS estado
FROM ni_he_tokens_revision
WHERE semana_piloto = '2026-06-24_2026-06-30'
ORDER BY ultimo_acceso DESC;

-- Ver notificaciones enviadas
SELECT
    supervisor_nombre,
    departamento,
    canal,
    estatus,
    fecha_creacion,
    fecha_envio,
    error_envio
FROM ni_he_notificaciones_revision
WHERE semana_piloto = '2026-06-24_2026-06-30'
ORDER BY fecha_creacion DESC;
```

---

## 🔄 Flujo de Token en Sesión

```
1. Supervisor recibe correo con:
   http://192.168.39.122:8009/he-control?token=abc123

2. Hace clic → GET /he-control?token=abc123

3. Backend valida token en BD:
   SELECT * FROM ni_he_tokens_revision
   WHERE token = 'abc123'
   AND activo = 1
   AND fecha_expiracion >= NOW()

4. Si válido → Carga automáticamente:
   - fecha_inicio, fecha_fin (24-30 junio)
   - departamento (ACABADO)
   - supervisor_numero (para auditoría)
   - Registra: ultimo_acceso = NOW()

5. Template recibe token → Lo inserta en todos los formularios como hidden

6. Supervisor confirma/rechaza/ajusta evento:
   POST /he-control/confirmar?token=abc123

7. Servidor registra acción y redirige:
   GET /he-control?fecha_inicio=...&token=abc123

8. Token se mantiene en URL durante TODA la sesión

9. Cuando fecha_expiracion >= NOW() no es válido:
   → Error: "La liga de revisión no es válida o ya expiró."
```

---

## 📊 Tabla de Comparación: Token vs Login Formal

| Aspecto | Token | Login Formal |
|--------|-------|-------------|
| **Tiempo** | ⏱️ Horas | ⏱️ Semanas |
| **Complejidad** | 🟢 Mínima | 🔴 Alta |
| **Para piloto** | 🟢 Perfecto | 🟡 Innecesario |
| **Validar UX** | 🟢 Rápido | 🟡 Lento |
| **Auditoría** | 🟡 Básica | 🟢 Completa |
| **Escalable** | 🟡 A corto plazo | 🟢 Permanente |

**Recomendación**: Usa token AHORA para piloto. Login formal DESPUÉS si aplica.

---

## ⚡ Quick Start

```bash
# 1. Crear tablas
sqlcmd -S servidor -d bd -i create_tokens.sql

# 2. Generar tokens
sqlcmd -S servidor -d bd << EOF
EXEC sp_ni_he_generar_tokens_revision
    @fecha_inicio = '2026-06-24',
    @fecha_fin = '2026-06-30',
    @semana_piloto = '2026-06-24_2026-06-30';
EOF

# 3. Ver tokens
sqlcmd -S servidor -d bd << EOF
SELECT token, supervisor_nombre, supervisor_email
FROM ni_he_tokens_revision
WHERE semana_piloto = '2026-06-24_2026-06-30'
  AND activo = 1;
EOF

# 4. Enviar correos (manual por ahora)
# - Copiar tokens
# - Crear URL: http://192.168.39.122:8009/he-control?token=XXX
# - Enviar a supervisores
```

---

## ✨ Archivos Relacionados

```
✅ app/routes/he_control.py        → Token auth en backend
✅ app/templates/he_control.html   → Token en formularios frontend
✅ app/templates/error.html        → Página de error
✅ create_tokens.sql               → Tablas + SP (completo)
✅ TOKEN_AUTH_GUIDE.md             → Esta documentación
```

---

## 📝 Notas

- No duplicar tokens para mismo supervisor en mismo periodo
- Token alfanumérico único de 32+ caracteres
- Expira automáticamente en 7 días
- Se puede desactivar manualmente si finaliza antes
- Registra último acceso para auditoría
- Tabla de notificaciones permite reenvío y seguimiento


