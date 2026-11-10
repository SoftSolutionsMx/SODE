@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================================================
echo   SODE - PREPARACION DE ENTORNO DE PRUEBAS DE ACEPTACION E INTEGRACION
echo ============================================================================

cd /d "%~dp0"

set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_CMD=venv\Scripts\python.exe"
)

echo [1/3] Verificando interprete de Python: %PYTHON_CMD%
"%PYTHON_CMD%" --version
if errorlevel 1 (
    echo [ERROR] No se encontro una instalacion valida de Python.
    exit /b 1
)

echo.
echo [2/3] Aplicando migraciones de base de datos...
"%PYTHON_CMD%" manage.py migrate --noinput
if errorlevel 1 (
    echo [ERROR] Fallo al ejecutar las migraciones.
    exit /b 1
)

echo.
echo [3/3] Cargando datos sinteticos de aceptacion (seed_acceptance_data)...
if "%~1"=="" (
    "%PYTHON_CMD%" manage.py seed_acceptance_data
) else (
    "%PYTHON_CMD%" manage.py seed_acceptance_data --real-email "%~1"
)
if errorlevel 1 (
    echo [ERROR] Fallo al cargar los datos de prueba.
    exit /b 1
)

echo.
echo ============================================================================
echo   ENTORNO DE PRUEBAS LISTO
echo   - Para iniciar el servidor: %PYTHON_CMD% manage.py runserver
echo   - Para ejecutar las pruebas: %PYTHON_CMD% manage.py test
echo ============================================================================
exit /b 0
