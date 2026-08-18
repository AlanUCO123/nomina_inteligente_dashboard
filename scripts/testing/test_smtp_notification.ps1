#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Script para probar configuración SMTP de NOVA HE Control
    
.DESCRIPTION
    Permite:
    1. Configurar variables de entorno SMTP
    2. Crear notificación de prueba en BD
    3. Llamar ruta de envío de email
    4. Verificar estado
    
.EXAMPLE
    .\test_smtp_notification.ps1 -Action setup
    .\test_smtp_notification.ps1 -Action test
    .\test_smtp_notification.ps1 -Action check
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('setup', 'test', 'check', 'full')]
    [string]$Action = 'full',
    
    [Parameter(Mandatory=$false)]
    [string]$SmtpServer = "smtp.gmail.com",
    
    [Parameter(Mandatory=$false)]
    [int]$SmtpPort = 587,
    
    [Parameter(Mandatory=$false)]
    [string]$SmtpUser,
    
    [Parameter(Mandatory=$false)]
    [string]$SmtpPassword,
    
    [Parameter(Mandatory=$false)]
    [string]$SmtpFrom = "nova@wyny.mx",
    
    [Parameter(Mandatory=$false)]
    [string]$TestEmail = "iracheta@wyny.mx"
)

$ErrorActionPreference = "Continue"

# Colores para output
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Error { Write-Host $args -ForegroundColor Red }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }

Write-Info "
╔════════════════════════════════════════════════════════════════╗
║  PRUEBA DE CONFIGURACIÓN SMTP - NOVA HE Control               ║
╚════════════════════════════════════════════════════════════════╝
"

# ============================================================================
# PASO 1: CONFIGURACIÓN SMTP
# ============================================================================

if ($Action -in @('setup', 'full')) {
    Write-Info "
📋 PASO 1: Configurar Variables de Entorno SMTP
═════════════════════════════════════════════════"
    
    if (-not $SmtpUser) {
        $SmtpUser = Read-Host "Usuario SMTP (ej: tu@gmail.com)"
    }
    
    if (-not $SmtpPassword) {
        $SecurePassword = Read-Host "Contraseña SMTP" -AsSecureString
        $SmtpPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [System.Runtime.InteropServices.Marshal]::SecureStringToCoTaskMemUnicode($SecurePassword)
        )
    }
    
    # Configurar variables de entorno en sesión actual
    $env:SMTP_SERVER = $SmtpServer
    $env:SMTP_PORT = $SmtpPort
    $env:SMTP_USER = $SmtpUser
    $env:SMTP_PASSWORD = $SmtpPassword
    $env:SMTP_FROM = $SmtpFrom
    
    Write-Success "✓ Variables configuradas:"
    Write-Host "  - SMTP_SERVER: $SmtpServer"
    Write-Host "  - SMTP_PORT: $SmtpPort"
    Write-Host "  - SMTP_USER: $SmtpUser"
    Write-Host "  - SMTP_FROM: $SmtpFrom"
    Write-Host ""
}

# ============================================================================
# PASO 2: CREAR NOTIFICACIÓN DE PRUEBA EN BD
# ============================================================================

if ($Action -in @('test', 'full')) {
    Write-Info "
📧 PASO 2: Crear Notificación de Prueba en BD
═════════════════════════════════════════════════"
    
    $sqlInsert = @"
INSERT INTO ni_he_notificaciones_revision (
    fecha_inicio,
    fecha_fin,
    semana_piloto,
    supervisor_numero,
    supervisor_nombre,
    supervisor_email,
    departamento,
    canal,
    destino,
    asunto,
    mensaje,
    estatus
)
VALUES (
    '2026-06-24',
    '2026-06-30',
    '2026-06-24_2026-06-30',
    99999,
    'SUPERVISOR PRUEBA',
    'supervisor@empresa.com',
    'ACABADO',
    'EMAIL',
    '$TestEmail',
    'Prueba - Control HE en Línea NOVA',
    'Buen día.`n`nEste es un correo de prueba del sistema NOVA de Control de HE en Línea.`n`nFecha: ' + CONVERT(VARCHAR(10), GETDATE(), 120) + '`n`nSi recibe este correo, la configuración SMTP está funcionando correctamente.',
    'PENDIENTE'
);

SELECT TOP 1 
    id,
    supervisor_nombre,
    destino,
    asunto,
    estatus,
    fecha_creacion
FROM ni_he_notificaciones_revision
WHERE asunto = 'Prueba - Control HE en Línea NOVA'
ORDER BY fecha_creacion DESC;
"@
    
    Write-Host "SQL que se ejecutaría:"
    Write-Host "──────────────────────────" -ForegroundColor DarkGray
    Write-Host $sqlInsert -ForegroundColor DarkGray
    Write-Host ""
    
    $continuar = Read-Host "¿Ejecutar SQL para crear notificación? (s/n)"
    if ($continuar -eq 's') {
        Write-Info "Copia el SQL anterior y ejecuta en SQL Server Management Studio o sqlcmd"
    }
}

# ============================================================================
# PASO 3: PROBAR RUTA DE ENVÍO
# ============================================================================

if ($Action -in @('test', 'full')) {
    Write-Info "
🌐 PASO 3: Probar Ruta de Envío /he-control/enviar-notificacion-prueba
═══════════════════════════════════════════════════════════════════════"
    
    Write-Host "Asegúrate de que:"
    Write-Host "  1. ✓ Servidor uvicorn está corriendo (python runserver.py)"
    Write-Host "  2. ✓ Variables de entorno SMTP están configuradas"
    Write-Host "  3. ✓ Notificación PENDIENTE existe en BD"
    Write-Host ""
    
    $serverRunning = $false
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8009/he-control" -Method Get -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $serverRunning = $true
        }
    } catch {
        $serverRunning = $false
    }
    
    if (-not $serverRunning) {
        Write-Error "✗ Servidor NO está corriendo en http://localhost:8009"
        Write-Warning "Ejecuta primero: python runserver.py"
        exit 1
    }
    
    Write-Success "✓ Servidor está corriendo"
    Write-Host ""
    
    $continuar = Read-Host "¿Llamar a ruta de envío de email? (s/n)"
    if ($continuar -eq 's') {
        Write-Info "Llamando POST /he-control/enviar-notificacion-prueba..."
        
        try {
            $response = Invoke-RestMethod `
                -Uri "http://localhost:8009/he-control/enviar-notificacion-prueba" `
                -Method Post `
                -ContentType "application/json" `
                -ErrorAction Stop
            
            if ($response.ok) {
                Write-Success "✓ Email enviado exitosamente"
                Write-Host "  Mensaje: $($response.mensaje)"
                Write-Host "  ID: $($response.notificacion_id)"
            } else {
                Write-Error "✗ Error: $($response.mensaje)"
            }
        } catch {
            Write-Error "✗ Error llamando ruta: $_"
        }
    }
}

# ============================================================================
# PASO 4: VERIFICAR ESTADO EN BD
# ============================================================================

if ($Action -in @('check', 'full')) {
    Write-Info "
✅ PASO 4: Verificar Estado en BD
═══════════════════════════════════"
    
    Write-Host "Para verificar el estado, ejecuta en SQL Server:"
    Write-Host ""
    Write-Host "-- Ver notificación enviada" -ForegroundColor DarkGray
    Write-Host @"
SELECT TOP 5
    id,
    supervisor_nombre,
    destino,
    asunto,
    estatus,
    fecha_creacion,
    fecha_envio,
    error_envio
FROM ni_he_notificaciones_revision
WHERE asunto LIKE 'Prueba%'
ORDER BY fecha_creacion DESC;
"@ -ForegroundColor DarkGray
    
    Write-Host ""
    Write-Host "Resultados esperados:" -ForegroundColor Yellow
    Write-Host "  - estatus: 'ENVIADA' ✓"
    Write-Host "  - fecha_envio: NO nulo ✓"
    Write-Host "  - error_envio: NULL ✓"
}

# ============================================================================
# RESUMEN FINAL
# ============================================================================

Write-Info "
📋 RESUMEN
═══════════════════════════════════════════════════════════════"

Write-Host @"
Configuración SMTP:
  - Servidor: $SmtpServer
  - Puerto: $SmtpPort
  - Usuario: $SmtpUser
  - Email origen: $SmtpFrom
  - Email prueba: $TestEmail

Archivos de referencia:
  - SMTP_CONFIG_GUIDE.md
  - TOKEN_AUTH_GUIDE.md
  - CONSOLIDATION_COMPLETE.md

Próximos pasos:
  1. Configurar permanentemente en .env
  2. Crear job/scheduler para envíos automáticos
  3. Generar tokens y notificaciones para supervisores
  4. Enviar ligas a supervisores
"@

Write-Success "
✓ Configuración de prueba completada
"
