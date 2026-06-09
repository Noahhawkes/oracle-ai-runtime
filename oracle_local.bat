@echo off
title ORACLE.AI
cd /d "%~dp0"
set LOCAL_MODE=true

ollama list >nul 2>&1
if errorlevel 1 (
    start /min "" ollama serve
    timeout /t 4 /nobreak >nul
)

python core/oracle.py
pause
