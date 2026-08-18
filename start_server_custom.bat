@echo off
REM Script para iniciar el servidor con puerto personalizado
REM Uso: start_server_custom.bat [puerto]
REM Ejemplo: start_server_custom.bat 8010

setlocal enabledelayedexpansion

REM Cambiar al directorio del proyecto
cd /d "%~dp0"

REM Obtener puerto del parámetro o usar 8009 por defecto
set puerto=%1
if "!puerto!"=="" set puerto=8009

REM Validar que sea un número
if not "!puerto!" geq 1000 (
    if not "!puerto!" leq 65535 (
        echo ERROR: El puerto debe estar entre 1000 y 65535
        echo Uso: start_server_custom.bat [puerto]
        echo Ejemplo: start_server_custom.bat 8010
        pause
        exit /b 1
    )
)

cls
echo =====================================
echo Iniciando Servidor - Nómina Inteligente
echo Puerto: !puerto!
echo =====================================
echo.

REM Ejecutar el servidor
python runserver.py --port !puerto!

REM Si hay error, mostrar mensaje
if errorlevel 1 (
    echo.
    echo ERROR: No se pudo iniciar el servidor en puerto !puerto!
    echo Verifica que:
    echo   - Python esté instalado
    echo   - El puerto !puerto! esté disponible
    echo   - La ruta sea correcta
    pause
)

endlocal
