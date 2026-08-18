@echo off
REM Script para iniciar el servidor con reinicio automático en caso de error
REM Incluye logging y trazabilidad

setlocal enabledelayedexpansion

REM Cambiar al directorio del proyecto
cd /d "%~dp0"

REM Crear carpeta de logs si no existe
if not exist "logs" mkdir logs

REM Obtener fecha y hora para el log
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c-%%a-%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a-%%b)

set logfile=logs\server_%mydate%_%mytime%.log

cls
echo =====================================
echo Iniciando Servidor - Nómina Inteligente
echo Puerto: 8009
echo Log: %logfile%
echo =====================================
echo.

REM Mostrar línea en el log
echo [%mydate% %mytime%] Iniciando servidor... >> "%logfile%"

REM Ejecutar el servidor
python runserver.py --port 8009 >> "%logfile%" 2>&1

REM Si hay error, reintentar
if errorlevel 1 (
    echo.
    echo ERROR: El servidor se detuvo inesperadamente
    echo Se intentará reiniciar en 5 segundos...
    echo [%mydate% %mytime%] Error detectado, reintentando... >> "%logfile%"
    timeout /t 5
    goto restart
)

goto end

:restart
python runserver.py --port 8009 >> "%logfile%" 2>&1
goto restart

:end
echo [%mydate% %mytime%] Servidor detenido >> "%logfile%"
pause

endlocal
