@echo off
setlocal enabledelayedexpansion


title Video-to-SRT Launcher

set NO_PROXY=127.0.0.1,localhost
set no_proxy=127.0.0.1,localhost

cd /d "%~dp0"

set BACKEND_LOG=%~dp0temp\backend.log
if not exist "%~dp0temp" mkdir "%~dp0temp" >nul 2>&1
if exist "%BACKEND_LOG%" del /f /q "%BACKEND_LOG%" >nul 2>&1

echo ======================================
echo Video-to-SRT Launcher
echo ======================================
echo.

echo [INFO] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    exit /b 1
)

python -c "import psutil, requests" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing system dependencies...
    pip install psutil requests
)

python -c "import fastapi,uvicorn,starlette,pydantic; import sse_starlette, multipart" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing web dependencies...
    pip install fastapi uvicorn[standard] sse-starlette python-multipart
)

echo [INFO] Starting backend...
start "Backend" /MIN cmd /c "cd /d %~dp0backend\app && python main.py > ..\..\temp\backend.log 2>&1"

echo [INFO] Waiting for backend...
set /a retries=0
:wait_backend
timeout /t 1 >nul
netstat -an | find ":8000 " | find "LISTENING" >nul
if not errorlevel 1 goto backend_ok

set /a retries+=1
if !retries! geq 30 (
    echo [ERROR] Backend timeout
    if exist "%BACKEND_LOG%" type "%BACKEND_LOG%"
    exit /b 1
)
goto wait_backend

:backend_ok
echo [OK] Backend started

if not exist "%~dp0frontend\node_modules" (
    echo [INFO] Installing frontend deps...
    cd /d "%~dp0frontend"
    npm install
    cd /d "%~dp0"
)

echo [INFO] Starting frontend...
start "Frontend" /MIN cmd /c "cd /d %~dp0frontend && npm run dev"

echo [INFO] Waiting for frontend...
set /a retries=0
:wait_frontend
timeout /t 1 >nul
netstat -an | find ":5174 " | find "LISTENING" >nul
if not errorlevel 1 (
    set frontend_port=5174
    goto frontend_ok
)
netstat -an | find ":5175 " | find "LISTENING" >nul
if not errorlevel 1 (
    set frontend_port=5175
    goto frontend_ok
)

set /a retries+=1
if !retries! geq 30 (
    echo [ERROR] Frontend timeout
    exit /b 1
)
goto wait_frontend

:frontend_ok
echo [OK] Frontend started on !frontend_port!

start http://localhost:!frontend_port!

echo.
echo ======================================
echo Services running:
echo Frontend: http://localhost:!frontend_port!
echo Backend:  http://127.0.0.1:8000
echo ======================================
echo.
echo Press any key to stop...
pause >nul

:: 清理进程
echo.
echo Stopping...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5174') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5175') do (
    taskkill /F /PID %%a >nul 2>&1
)
exit /b 0

:error_exit
echo.
echo Error
pause
exit /b 1
