@echo off
setlocal
cd /d "%~dp0"
title xBloom bleUI Server v0.8.8

:: ========================================================
:: [PORT SETTING] Default: 8000
:: If port 8000 is in use, change the number below:
:: (You can also run with argument: run.bat 8080)
:: ========================================================
set PORT=8000
if not "%~1"=="" set PORT=%~1

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

echo [ERROR] Python not found.
echo Please install Python 3.10+ or download the Portable edition.
echo (https://www.python.org)
echo.
pause
exit /b 1

:RUN
"%PY_CMD%" run.py --port %PORT%
if %errorlevel% neq 0 pause
