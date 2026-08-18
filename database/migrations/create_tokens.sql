-- ====================================================================
-- Script: Crear Tablas y Procedimientos para Tokens de Revisión HE
-- Propósito: Tabla de tokens, notificaciones y SP para generar tokens
-- Diseño: Por supervisor/departamento/periodo con HE pendiente
-- ====================================================================

-- 1. TABLA: ni_he_tokens_revision
-- Almacena tokens únicos por supervisor/departamento/periodo
-- Permite acceso seguro al panel de control HE en línea

IF OBJECT_ID('ni_he_tokens_revision', 'U') IS NULL
BEGIN
    CREATE TABLE ni_he_tokens_revision (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        token VARCHAR(100) NOT NULL UNIQUE,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE NOT NULL,
        semana_piloto VARCHAR(30) NULL,
        supervisor_numero VARCHAR(20) NULL,
        supervisor_nombre VARCHAR(200) NULL,
        supervisor_email VARCHAR(200) NULL,
        gerente_numero VARCHAR(20) NULL,
        gerente_nombre VARCHAR(200) NULL,
        gerente_email VARCHAR(200) NULL,
        departamento VARCHAR(150) NULL,
        rol_acceso VARCHAR(30) NOT NULL DEFAULT 'SUPERVISOR',
        activo BIT NOT NULL DEFAULT 1,
        fecha_expiracion DATETIME NULL,
        fecha_creacion DATETIME NOT NULL DEFAULT GETDATE(),
        ultimo_acceso DATETIME NULL
    );
    
    PRINT '✓ Tabla ni_he_tokens_revision creada';
END
ELSE
    PRINT '✓ Tabla ni_he_tokens_revision ya existe';

GO

-- 2. TABLA: ni_he_notificaciones_revision
-- Registra notificaciones enviadas (email/WhatsApp/SMS) a supervisores
-- Permite auditoría y reenvíos

IF OBJECT_ID('ni_he_notificaciones_revision', 'U') IS NULL
BEGIN
    CREATE TABLE ni_he_notificaciones_revision (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        token_id BIGINT NULL,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE NOT NULL,
        semana_piloto VARCHAR(30) NULL,
        supervisor_numero VARCHAR(20) NULL,
        supervisor_nombre VARCHAR(200) NULL,
        supervisor_email VARCHAR(200) NULL,
        departamento VARCHAR(150) NULL,
        eventos_pendientes INT NOT NULL DEFAULT 0,
        empleados INT NOT NULL DEFAULT 0,
        minutos_detectados INT NOT NULL DEFAULT 0,
        canal VARCHAR(30) NOT NULL DEFAULT 'EMAIL',
        destino VARCHAR(200) NULL,
        asunto NVARCHAR(300) NULL,
        mensaje NVARCHAR(MAX) NULL,
        estatus VARCHAR(40) NOT NULL DEFAULT 'PENDIENTE',
        fecha_creacion DATETIME NOT NULL DEFAULT GETDATE(),
        fecha_envio DATETIME NULL,
        error_envio NVARCHAR(1000) NULL
    );
    
    PRINT '✓ Tabla ni_he_notificaciones_revision creada';
END
ELSE
    PRINT '✓ Tabla ni_he_notificaciones_revision ya existe';

GO

-- 3. PROCEDIMIENTO: sp_ni_he_generar_tokens_revision
-- Genera un token por supervisor/departamento/periodo con HE pendiente
-- Evita duplicar tokens para el mismo supervisor en el mismo periodo

IF OBJECT_ID('sp_ni_he_generar_tokens_revision', 'P') IS NOT NULL
    DROP PROCEDURE sp_ni_he_generar_tokens_revision;

GO

CREATE PROCEDURE sp_ni_he_generar_tokens_revision
    @fecha_inicio DATE,
    @fecha_fin DATE,
    @semana_piloto VARCHAR(30)
AS
BEGIN
    SET NOCOUNT ON;
    
    INSERT INTO ni_he_tokens_revision (
        token,
        fecha_inicio,
        fecha_fin,
        semana_piloto,
        supervisor_numero,
        supervisor_nombre,
        supervisor_email,
        gerente_numero,
        gerente_nombre,
        gerente_email,
        departamento,
        rol_acceso,
        fecha_expiracion
    )
    SELECT
        CONVERT(VARCHAR(100), NEWID()) AS token,
        @fecha_inicio,
        @fecha_fin,
        @semana_piloto,
        e.supervisor_numero,
        e.supervisor_nombre,
        MAX(e.supervisor_email),
        MAX(e.gerente_numero),
        MAX(e.gerente_nombre),
        MAX(e.gerente_email),
        e.departamento,
        'SUPERVISOR',
        DATEADD(DAY, 7, GETDATE())
    FROM ni_he_eventos_jornada e
    WHERE e.fecha_operativa BETWEEN @fecha_inicio AND @fecha_fin
      AND e.semana_piloto = @semana_piloto
      AND e.estatus = 'PENDIENTE'
      AND e.supervisor_numero IS NOT NULL
      AND NOT EXISTS (
            SELECT 1
            FROM ni_he_tokens_revision t
            WHERE t.fecha_inicio = @fecha_inicio
              AND t.fecha_fin = @fecha_fin
              AND t.semana_piloto = @semana_piloto
              AND t.supervisor_numero = e.supervisor_numero
              AND t.departamento = e.departamento
              AND t.activo = 1
      )
    GROUP BY
        e.supervisor_numero,
        e.supervisor_nombre,
        e.departamento;
    
    PRINT '✓ Tokens generados exitosamente';
END;

GO

-- 4. CONSULTA: Ver tokens generados con detalles
-- Muestra: token, supervisor, departamento, eventos pendientes, link de revisión

PRINT '
========================================================================
TOKENS GENERADOS - Resumen para Envío
========================================================================
';

SELECT
    t.token,
    t.supervisor_numero,
    t.supervisor_nombre,
    t.supervisor_email,
    t.departamento,
    COUNT(e.id) AS eventos_pendientes,
    COUNT(DISTINCT e.numero_empleado) AS empleados,
    CAST(SUM(e.minutos_detectados) / 60.0 AS DECIMAL(10,2)) AS horas_detectadas,
    CONCAT(
        'http://192.168.39.122:8009/he-control?token=', t.token
    ) AS link_revision,
    t.fecha_expiracion,
    DATEDIFF(HOUR, GETDATE(), t.fecha_expiracion) AS horas_valido
FROM ni_he_tokens_revision t
INNER JOIN ni_he_eventos_jornada e
    ON e.supervisor_numero = t.supervisor_numero
   AND e.departamento = t.departamento
   AND e.fecha_operativa BETWEEN t.fecha_inicio AND t.fecha_fin
   AND e.semana_piloto = t.semana_piloto
   AND e.estatus = 'PENDIENTE'
WHERE t.semana_piloto = '2026-06-24_2026-06-30'
GROUP BY
    t.token,
    t.supervisor_numero,
    t.supervisor_nombre,
    t.supervisor_email,
    t.departamento,
    t.fecha_expiracion
ORDER BY t.supervisor_nombre;

GO

-- ====================================================================
-- PARA EJECUTAR: Generar tokens automáticamente
-- ====================================================================
-- Descomentar cuando esté listo para generar:
/*
EXEC sp_ni_he_generar_tokens_revision
    @fecha_inicio = '2026-06-24',
    @fecha_fin = '2026-06-30',
    @semana_piloto = '2026-06-24_2026-06-30';
*/

GO

PRINT '
========================================================================
Tablas y procedimientos listos.

PRÓXIMOS PASOS:
1. Ejecutar: EXEC sp_ni_he_generar_tokens_revision ...
2. Copiar tokens desde consulta arriba
3. Enviar liga a supervisores por correo/WhatsApp
========================================================================
';

    );

-- 3. CONSULTAR TOKENS ACTIVOS
SELECT 
    token_id,
    token,
    supervisor_numero,
    supervisor_nombre,
    departamento,
    rol_acceso,
    fecha_inicio,
    fecha_fin,
    fecha_expiracion,
    'http://192.168.39.122:8009/he-control?token=' + token AS url_revision,
    notas
FROM ni_he_tokens_revision
WHERE activo = 1
  AND (fecha_expiracion IS NULL OR fecha_expiracion >= GETDATE())
ORDER BY fecha_creacion DESC;

-- 4. CONSULTAR TOKENS EXPIRADOS
SELECT 
    token_id,
    token,
    supervisor_nombre,
    departamento,
    fecha_expiracion,
    'EXPIRADO' AS estado
FROM ni_he_tokens_revision
WHERE activo = 1
  AND fecha_expiracion < GETDATE()
ORDER BY fecha_expiracion DESC;

-- 5. DESACTIVAR TOKEN (cuando supervisor termine revisión)
-- UPDATE ni_he_tokens_revision SET activo = 0 WHERE token = 'xxx';

-- 6. VERIFICAR TABLA
SELECT COUNT(*) AS total_tokens FROM ni_he_tokens_revision;
SELECT COUNT(*) AS tokens_activos FROM ni_he_tokens_revision WHERE activo = 1 AND (fecha_expiracion IS NULL OR fecha_expiracion >= GETDATE());
