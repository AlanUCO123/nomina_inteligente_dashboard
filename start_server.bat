@echo off
REM Script para iniciar el servidor de Nómina Inteligente Dashboard
REM Puerto: 8009

setlocal enabledelayedexpansion

REM Cambiar al directorio del proyecto
cd /d "%~dp0"

REM Mostrar mensaje de bienvenida
cls
echo =====================================
echo Iniciando Servidor - Nómina Inteligente
echo Puerto: 8009
echo =====================================
echo.

REM Ejecutar el servidor
python runserver.py --port 8009

REM Si hay error, mostrar mensaje
if errorlevel 1 (
    echo.
    echo ERROR: No se pudo iniciar el servidor
    echo Verifica que Python esté instalado y la ruta es correcta
    pause
)

endlocal
