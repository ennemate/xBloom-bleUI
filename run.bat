@echo off
setlocal
cd /d "%~dp0"
title xBloom bleUI Server v0.8.0

set "PY_CMD="

if exist "%~dp0python\python.exe" (
    set "PY_CMD=%~dp0python\python.exe"
    goto :RUN
)

if exist "%~dp0runtime\python.exe" (
    set "PY_CMD=%~dp0runtime\python.exe"
    goto :RUN
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    goto :RUN
)

echo [ERROR] Python을 찾을 수 없습니다.
echo 파이썬(Python 3.10+)을 설치하거나 포터블 버전을 다운로드해주세요.
echo (https://www.python.org)
echo.
pause
exit /b 1

:RUN
"%PY_CMD%" run.py %*
if %errorlevel% neq 0 pause
