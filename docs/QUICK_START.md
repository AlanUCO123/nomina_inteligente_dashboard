# 🎯 INICIO RÁPIDO - Token + SMTP + Panel HE Control

## ⚡ 5 Pasos para Piloto Inmediato

### Paso 1: Crear Tablas en BD (5 min)
```bash
sqlcmd -S SERVIDOR -d BASEDATOS -i create_tokens.sql
```

**Output esperado**:
```
✓ Tabla ni_he_tokens_revision creada
✓ Tabla ni_he_notificaciones_revision creada
✓ Procedimiento sp_ni_he_generar_tokens_revision creado
```

---

### Paso 2: Generar Tokens Automáticamente (2 min)
```sql
EXEC sp_ni_he_generar_tokens_revision
    @fecha_inicio = '2026-06-24',
    @fecha_fin = '2026-06-30',
    @semana_piloto = '2026-06-24_2026-06-30';
```

**Resultado**: Crea 1 token por cada supervisor con HE PENDIENTE

**Ver tokens**:
```sql
SELECT supervisor_nombre, token, supervisor_email 
FROM ni_he_tokens_revision 
WHERE semana_piloto = '2026-06-24_2026-06-30'
  AND activo = 1;
```

---

### Paso 3: Configurar SMTP (5 min)

#### Opción A: Gmail (RECOMENDADO PARA PRUEBAS)
1. Ir a https://myaccount.google.com/apppasswords
2. Generar contraseña de app
3. En PowerShell:
```powershell
$env:SMTP_SERVER = "smtp.gmail.com"
$env:SMTP_PORT = "587"
$env:SMTP_USER = "tu@gmail.com"
$env:SMTP_PASSWORD = "xxxxxxxx xxxx xxxx xxxx"  # Sin espacios
$env:SMTP_FROM = "tu@gmail.com"
```

#### Opción B: Office 365
```powershell
$env:SMTP_SERVER = "smtp.office365.com"
$env:SMTP_PORT = "587"
$env:SMTP_USER = "usuario@empresa.com"
$env:SMTP_PASSWORD = "tu_password"
$env:SMTP_FROM = "noreply@empresa.com"
```

**Ver archivo**: `SMTP_CONFIG_GUIDE.md` para más opciones

---

### Paso 4: Crear Notificación de Prueba (2 min)
```sql
INSERT INTO ni_he_notificaciones_revision (
    fecha_inicio, fecha_fin, semana_piloto,
    supervisor_numero, supervisor_nombre, supervisor_email,
    departamento, canal, destino, asunto, mensaje, estatus
)
VALUES (
    '2026-06-24', '2026-06-30', '2026-06-24_2026-06-30',
    99999, 'VERONICA PEREZ', 'veronica@empresa.com',
    'ACABADO', 'EMAIL', 'veronica@empresa.com',
    'Control HE - Piloto ACABADO',
    'Buen día Verónica, se detectaron HE pendientes de revisión. Liga: http://192.168.39.122:8009/he-control?token=...',
    'PENDIENTE'
);
```

---

### Paso 5: Probar Envío de Email (1 min)

#### Opción A: Navegador
1. Iniciar servidor: `python runserver.py` (con variables SMTP configuradas)
2. Abrir: http://localhost:8009/he-control/enviar-notificacion-prueba
3. Ver respuesta JSON

#### Opción B: PowerShell
```powershell
# Asegúrate de tener variables SMTP configuradas
# Luego:
Invoke-RestMethod `
    -Uri "http://localhost:8009/he-control/enviar-notificacion-prueba" `
    -Method Post
```

#### Opción C: Script automático
```bash
cd c:\proyectos\nomina_inteligente_dashboard
powershell -File test_smtp_notification.ps1 -Action full
```

**Respuesta esperada**:
```json
{
  "ok": true,
  "mensaje": "Correo enviado a veronica@empresa.com (VERONICA PEREZ)",
  "notificacion_id": 1
}
```

---

## ✅ Checklist Piloto Básico

```
PREPARACIÓN:
[ ] 1. create_tokens.sql ejecutado
[ ] 2. Tablas creadas en BD
[ ] 3. SP sp_ni_he_generar_tokens_revision existe

TOKENS:
[ ] 4. Ejecutar SP para generar tokens
[ ] 5. Tokens aparecen en tabla (SELECT)
[ ] 6. Token válido, único, alfanumérico

SMTP:
[ ] 7. Variables de entorno configuradas
[ ] 8. Notificación de prueba creada en BD
[ ] 9. Servidor iniciado con SMTP_* configurados
[ ] 10. Ruta devuelve {"ok": true}

AUDITORÍA:
[ ] 11. Email recibido en destino
[ ] 12. notificaciones_revision.estatus = 'ENVIADA'
[ ] 13. tokens_revision.ultimo_acceso registrado
```

---

## 🌐 Acceder al Panel con Token

```
URL: http://192.168.39.122:8009/he-control?token=ABC123DEF456

Qué sucede:
1. ✓ Valida token en BD
2. ✓ Registra ultimo_acceso
3. ✓ Carga filtros automáticamente (ACABADO, 24-30 junio)
4. ✓ Supervisor puede confirmar/rechazar/ajustar eventos
5. ✓ Token se mantiene en toda sesión
```

---

## 📝 Archivos de Referencia

```
create_tokens.sql              → Tablas + SP (ejecutar en SQL)
TOKEN_AUTH_GUIDE.md            → Guía completa tokens
SMTP_CONFIG_GUIDE.md           → Guía completa SMTP
CONSOLIDATION_COMPLETE.md      → Documentación consolidación
test_smtp_notification.ps1     → Script PowerShell interactivo
.env.example                   → Template de variables
```

---

## 🎯 Próximos Pasos Después de Pruebas

### Cuando el piloto funcione:
1. [ ] Generar tokens para todos supervisores ACABADO
2. [ ] Generar notificaciones con SQL INSERT o SP
3. [ ] Crear scheduler para envíos automáticos cada 5 min
4. [ ] Enviar ligas a supervisores reales
5. [ ] Monitorear acciones en BD (ultimo_acceso, cambios de estado)
6. [ ] Escalar a otros departamentos
7. [ ] Implementar login formal (opcional, después del piloto)

---

## ⚠️ Troubleshooting

**Problema**: Token inválido
```sql
-- Verificar
SELECT token, activo, fecha_expiracion, ultimo_acceso
FROM ni_he_tokens_revision
WHERE token = 'tu_token_aqui';

-- Re-activar si expiró
UPDATE ni_he_tokens_revision
SET fecha_expiracion = DATEADD(DAY, 7, GETDATE())
WHERE token = 'tu_token_aqui';
```

**Problema**: Email no se envía
```
1. Verificar variables SMTP_* estén configuradas:
   echo $env:SMTP_USER
   
2. Verificar credenciales son correctas
   
3. Revisar log de BD:
   SELECT error_envio FROM ni_he_notificaciones_revision 
   WHERE estatus = 'ERROR';
```

**Problema**: Notificación muestra "PENDIENTE"
```sql
-- Buscar notificaciones
SELECT * FROM ni_he_notificaciones_revision
WHERE estatus = 'PENDIENTE'
ORDER BY id DESC;

-- Si no hay ninguna, crear una:
INSERT INTO ni_he_notificaciones_revision ...
```

---

## 🚀 ¡LISTO!

Si completaste todos los pasos arriba con ✓, el sistema está **100% funcional** para:
- ✅ Acceso seguro por token
- ✅ Envío de notificaciones por email
- ✅ Panel de control HE en línea
- ✅ Confirmación/rechazo/ajuste de HE

**Próximo**: Enviar a supervisores reales 📧
