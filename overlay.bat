@echo off
title ORACLE.AI Overlay OS
cd /d "%~dp0"
set LOCAL_MODE=true
pythonw core\overlay.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo Overlay failed to start. Trying python instead of pythonw...
    python core\overlay.py
    pause
)
