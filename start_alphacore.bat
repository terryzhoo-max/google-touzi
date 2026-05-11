@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title AlphaCore Quant Server

:: ====== CONFIG ======
if not defined PROJECT_DIR set "PROJECT_DIR=%~dp0"
if not defined HOST set "HOST=127.0.0.1"
if not defined PORT set "PORT=8888"
if not defined APP_MODULE set "APP_MODULE=data_engine:app"
set "OPEN_BROWSER=1"
if /i "%~1"=="--no-browser" set "OPEN_BROWSER=0"

echo.
echo ============================================================
echo    AlphaCore Insights Terminal  v2.0
echo    One-Click Server Launcher
echo ============================================================
echo.

:: ------ [1/4] Project Directory ------
echo [1/4] Checking project directory...

if not exist "%PROJECT_DIR%\data_engine.py" (
    echo [FATAL] data_engine.py not found at: %PROJECT_DIR%
    goto :error_exit
)
cd /d "%PROJECT_DIR%"
echo       OK - %PROJECT_DIR%

:: ------ [2/4] Python ------
echo [2/4] Checking Python...

python --version >nul 2>&1
if errorlevel 1 (
    echo [FATAL] Python not found! Install Python 3.10+
    echo         https://www.python.org/downloads/
    goto :error_exit
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo       OK - Python %PY_VER%

:: ------ [3/4] Dependencies ------
echo [3/4] Checking dependencies...

set "MISSING="

python -c "import fastapi" >nul 2>&1
if errorlevel 1 set "MISSING=!MISSING! fastapi"

python -c "import uvicorn" >nul 2>&1
if errorlevel 1 set "MISSING=!MISSING! uvicorn"

python -c "import pandas" >nul 2>&1
if errorlevel 1 set "MISSING=!MISSING! pandas"

python -c "import numpy" >nul 2>&1
if errorlevel 1 set "MISSING=!MISSING! numpy"

python -c "import requests" >nul 2>&1
if errorlevel 1 set "MISSING=!MISSING! requests"

if not "!MISSING!"=="" (
    echo [WARN] Missing:!MISSING!
    set /p "YN=       Auto-install? (Y/N): "
    if /i "!YN!"=="Y" (
        pip install -r requirements.txt -q
        if errorlevel 1 (
            echo [FATAL] Install failed. Run manually: pip install -r requirements.txt
            goto :error_exit
        )
        echo       OK - Dependencies installed
    ) else (
        echo [FATAL] Missing dependencies. Cannot start.
        goto :error_exit
    )
) else (
    echo       OK - All dependencies ready
)

:: ------ [4/4] Port Check ------
echo [4/4] Checking port %PORT%...

netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Port %PORT% is in use!
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
        set "OLD_PID=%%p"
        echo       Occupied by PID: %%p
    )
    set /p "YN=       Kill old process and restart? (Y/N): "
    if /i "!YN!"=="Y" (
        taskkill /F /PID !OLD_PID! >nul 2>&1
        timeout /t 2 /nobreak >nul
        echo       OK - Old process killed
    ) else (
        echo       Cancelled.
        goto :error_exit
    )
)
echo       OK - Port %PORT% available

:: ====== LAUNCH ======
echo.
echo ============================================================
echo   All checks passed - Starting AlphaCore Server...
echo ============================================================
echo.
echo   [ TERMINAL UI ]  http://%HOST%:%PORT%
echo   [ DATA ENGINE ]  http://%HOST%:%PORT%/api/macro/erp
echo   [ API DOCS ]     http://%HOST%:%PORT%/docs
echo.
echo   Press Ctrl+C to stop the server
echo ============================================================
echo.

:: Automatically open the browser unless --no-browser is passed
if "%OPEN_BROWSER%"=="1" start http://%HOST%:%PORT%

:: Start the unified FastAPI server
python -m uvicorn %APP_MODULE% --host %HOST% --port %PORT%

:: ====== EXIT HANDLING ======
echo.
if errorlevel 1 (
    echo [ERROR] Server exited abnormally (code: %errorlevel%)
) else (
    echo [INFO] AlphaCore server stopped normally.
)
goto :end

:error_exit
echo.
echo ============================================================
echo   STARTUP FAILED - Check errors above
echo ============================================================

:end
echo.
pause
endlocal
