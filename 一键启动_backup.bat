@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置标题
title Video-to-SRT 一键启动器

:: 设置代理绕过本地服务 (Clash 等)
set NO_PROXY=127.0.0.1,localhost
secho ==========================================================
echo 服务启动完成！
echo 前端地址: http://localhost:!frontend_port!
echo 后端地址: http://127.0.0.1:8000  
echo 后端日志: %BACKEND_LOG%
echo ==========================================================
echo.
echo 注意事项：
echo    保持此窗口打开以监控服务状态
echo    关闭此窗口会自动停止所有服务
echo    如遇问题，请检查防火墙和杀毒软件设置
echo    模型预加载在后台运行，前端会显示加载进度127.0.0.1,localhost

:: 确保在正确的目录
cd /d "%~dp0"

:: 日志文件
set BACKEND_LOG=%~dp0temp\backend.log
if not exist "%~dp0temp" mkdir "%~dp0temp" >nul 2>&1
if exist "%BACKEND_LOG%" del /f /q "%BACKEND_LOG%" >nul 2>&1

echo ==========================================================
echo Video-to-SRT 启动器
echo ==========================================================
echo.

:: 检查并安装必要依赖
echo [信息] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 未安装或未加入PATH
    echo 请确保已安装Python并添加到系统PATH中
    goto :error_exit
)

python -c "import psutil, requests" >nul 2>&1
if errorlevel 1 (
    echo [信息] 安装必要的系统依赖包...
    pip install psutil requests
    if errorlevel 1 (
        echo [错误] 依赖包安装失败
        goto :error_exit
    )
)

:: 额外检查后端Web依赖（避免FastAPI/uvicorn缺失导致后端启动失败）
python -c "import fastapi,uvicorn,starlette,pydantic; import sse_starlette, multipart" >nul 2>&1
if errorlevel 1 (
    echo [信息] 安装后端Web依赖...
    pip install fastapi uvicorn[standard] sse-starlette python-multipart
    if errorlevel 1 (
        echo [错误] 后端Web依赖安装失败
        goto :error_exit
    )
)

:: 清理之前的进程
echo [信息] 清理之前的进程...
call "%~dp0清理进程.bat"

:: 启动后端服务（使用独立进程，避免信号传递）
echo [信息] 启动后端服务...
start "VideoToSRT-Backend" /MIN cmd /c "cd /d %~dp0backend\app && python -u main.py >> ..\..\temp\backend.log 2>&1"

:: 等待后端启动
echo [信息] 等待后端服务启动...
set /a retries=0
:wait_backend
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/api/ping' -TimeoutSec 2).StatusCode -eq 200 } catch { $false }" | findstr True >nul
if not errorlevel 1 goto backend_ready

set /a retries+=1
if !retries! geq 90 (
    echo [错误] 后端服务启动超时
    echo [调试] 后端日志(最近200行):
    powershell -NoProfile -Command "if (Test-Path '%BACKEND_LOG%') { Get-Content -Path '%BACKEND_LOG%' -Tail 200 } else { Write-Host '暂无日志' }"
    goto :error_exit
)

if !retries! geq 10 (
    echo [调试] 后端日志(最近50行):
    powershell -NoProfile -Command "if (Test-Path '%BACKEND_LOG%') { Get-Content -Path '%BACKEND_LOG%' -Tail 50 } else { Write-Host '暂无日志' }"
)

timeout /t 1 >nul
goto wait_backend

:backend_ready
echo [成功] 后端服务已启动

:: 后端就绪后，立即触发模型预加载（修复版：立即返回，不阻塞）
echo [信息] 启动模型预加载...
powershell -NoProfile -Command "try { $res = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/models/preload/start' -Method Post -TimeoutSec 10; if ($res.success) { Write-Host '[成功] 预加载已启动，后台运行中' } else { Write-Host '[警告] 预加载启动返回: ' $res.message } } catch { Write-Host '[提示] 预加载请求失败: ' $_ }"

:: 快速检查是否进入预加载状态（最多3秒，不强制等待）
echo [信息] 检查预加载状态...
set /a tries=0
:check_preloading
powershell -NoProfile -Command "try { $s = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/models/preload/status' -TimeoutSec 2; if ($s.success) { if ($s.data.is_preloading) { Write-Host '[信息] 后端已进入预加载状态' } else { Write-Host '[信息] 预加载状态检查完成' } } } catch { Write-Host '[警告] 无法获取预加载状态' }"
set /a tries+=1
if !tries! geq 3 goto continue_startup
timeout /t 1 >nul
goto check_preloading

:continue_startup
echo [信息] 继续启动流程...

:: 检查前端依赖
if not exist "%~dp0frontend\node_modules" (
    echo [信息] 安装前端依赖...
    cd /d "%~dp0frontend"
    npm install
    if errorlevel 1 (
        echo [错误] 前端依赖安装失败
        goto :error_exit
    )
    cd /d "%~dp0"
)

:: 启动前端服务（使用独立进程，避免信号传递）
echo [信息] 启动前端服务...
start "VideoToSRT-Frontend" /MIN cmd /c "cd /d %~dp0frontend && npm run dev"

:: 等待前端启动
echo [信息] 等待前端服务启动...
set /a retries=0
:wait_frontend
:: 检查5174端口
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing 'http://localhost:5174' -TimeoutSec 2).StatusCode -eq 200 } catch { $false }" | findstr True >nul
if not errorlevel 1 (
    set frontend_port=5174
    goto frontend_ready
)

:: 检查5175端口
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing 'http://localhost:5175' -TimeoutSec 2).StatusCode -eq 200 } catch { $false }" | findstr True >nul
if not errorlevel 1 (
    set frontend_port=5175
    goto frontend_ready
)

set /a retries+=1
if !retries! geq 60 (
    echo [错误] 前端服务启动超时
    goto :error_exit
)

timeout /t 1 >nul
goto wait_frontend

:frontend_ready
echo [成功] 前端服务已启动在端口 !frontend_port!

:: 打开浏览器
echo [信息] 打开浏览器...
start http://localhost:!frontend_port!

:: 等待系统稳定
echo [信息] 等待系统完全就绪...
timeout /t 3 >nul

echo.
echo ==========================================================
echo 服务启动完成！
echo 前端地址: http://localhost:!frontend_port!
echo 后端地址: http://127.0.0.1:8000  
echo 后端日志: %BACKEND_LOG%
echo ==========================================================
echo.
echo 注意事项：
echo    • 保持此窗口打开以监控服务状态
echo    • 关闭此窗口会自动停止所有服务
echo    • 如遇问题，请检查防火墙和杀毒软件设置
echo    • 模型预加载在后台运行，前端会显示加载进度
echo.

:: 简化的监控循环，避免编码问题
:monitor_loop
echo [监控] 检查服务状态... (按 Ctrl+C 退出)
timeout /t 10 >nul 2>&1
if errorlevel 1 goto :cleanup

:: 简单检查进程是否存在，避免复杂的网络请求
tasklist /FI "IMAGENAME eq python.exe" | find "python.exe" >nul
if errorlevel 1 (
    echo [警告] Python进程不存在，服务可能已停止
    goto :service_stopped
)

goto monitor_loop

:service_stopped
echo [错误] 服务意外停止，正在退出...
goto :cleanup

:cleanup
:: 清理进程
echo.
echo [信息] 正在停止服务...
call "%~dp0清理进程.bat"
echo [成功] 所有服务已停止
exit /b 0

:error_exit
echo.
echo [错误] 启动失败，请检查上述错误信息
echo 如果后端未启动，请查看日志: %BACKEND_LOG%
if exist "%BACKEND_LOG%" (
  echo [提示] 最近100行后端日志:
  powershell -NoProfile -Command "Get-Content -Path '%BACKEND_LOG%' -Tail 100"
)
pause
exit /b 1
