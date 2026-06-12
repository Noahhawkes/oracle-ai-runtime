@echo off
title ORACLE
cd /d "%~dp0"

:: Start Ollama in background only if not already running — no wait
ollama list >nul 2>&1
if errorlevel 1 start /min "" ollama serve

:: --fast: skip banner animation, go straight to prompt
python core/oracle.py --fast
pause
