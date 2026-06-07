@echo off
title ORACLE.AI
cd /d "%~dp0"

echo [ORACLE] Checking Ollama...
ollama list >nul 2>&1
if errorlevel 1 (
    echo [ORACLE] Starting Ollama engine...
    start /min "" ollama serve
    timeout /t 4 /nobreak >nul
) else (
    echo [ORACLE] Ollama already running.
)

python core/oracle.py
pause
