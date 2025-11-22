@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 设置标题
title Video-to-SRT 进程清理器 (修复版)

echo [信息] 正在清理所有相关进程...

:: 尝试优雅关闭后端服务
echo [信息] 尝试优雅关闭后端服务...
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/shutdown' -Method Post -TimeoutSec 5 | Out-Null; Write-Host '[成功] 后端服务已优雅关闭' } catch { Write-Host '[提示] 后端服务未响应，将强制终止' }" 2>nul

:: 等待一下让服务有时间关闭
timeout /t 2 >nul

echo [信息] 强制终止相关进程...

:: 终止Python进程
echo [信息] 终止Python进程...
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo csv ^| findstr /v "PID"') do (
    if not "%%i"=="" (
        taskkill /f /pid %%~i >nul 2>&1
    )
)

for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python3.exe" /fo csv ^| findstr /v "PID"') do (
    if not "%%i"=="" (
        taskkill /f /pid %%~i >nul 2>&1
    )
)

for /f "tokens=2" %%i in ('tasklist /fi "imagename eq pythonw.exe" /fo csv ^| findstr /v "PID"') do (
    if not "%%i"=="" (
        taskkill /f /pid %%~i >nul 2>&1
    )
)

:: 终止Node.js进程
echo [信息] 终止Node.js进程...
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq node.exe" /fo csv ^| findstr /v "PID"') do (
    if not "%%i"=="" (
        taskkill /f /pid %%~i >nul 2>&1
    )
)

for /f "tokens=2" %%i in ('tasklist /fi "imagename eq npm.exe" /fo csv ^| findstr /v "PID"') do (
    if not "%%i"=="" (
        taskkill /f /pid %%~i >nul 2>&1
    )
)

:: 清理占用端口的进程
echo [信息] 清理占用端口的进程...

:: 清理8000端口 (后端)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 清理5174端口 (前端)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5174') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 清理5175端口 (前端备用)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5175') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 清理3000端口 (可能的前端端口)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 额外清理：查找可能包含video-to-srt关键字的进程
echo [信息] 清理相关应用进程...
wmic process where "CommandLine like '%%video-to-srt%%' or CommandLine like '%%main.py%%'" delete >nul 2>&1

:: 等待进程完全退出
timeout /t 1 >nul

echo [成功] 进程清理完成

