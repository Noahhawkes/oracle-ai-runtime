@echo off
title ORACLE.AI
cd /d "%~dp0"
setlocal

set "RUNTIME_ROOT=%~dp0"
if "%RUNTIME_ROOT:~-1%"=="\" set "RUNTIME_ROOT=%RUNTIME_ROOT:~0,-1%"
if /I not "%RUNTIME_ROOT%"=="C:\Oracle\ORACLE.AI-runtime" (
    echo BOOT REFUSED: runtime root must be C:\Oracle\ORACLE.AI-runtime
    pause
    exit /b 1
)
if not exist "C:\Oracle\state" (
    echo BOOT REFUSED: state root unavailable: C:\Oracle\state
    pause
    exit /b 1
)
if not exist "C:\Oracle\state\boot_receipts" mkdir "C:\Oracle\state\boot_receipts"

set ORACLE_FORCE_LOCAL=true
set LOCAL_MODE=true

ollama list >nul 2>&1
if errorlevel 1 (
    start /min "" ollama serve
    timeout /t 4 /nobreak >nul
)

python core\boot_receipt.py --print-line
if errorlevel 1 (
    pause
    exit /b 1
)

python core/oracle.py
pause
endlocal
