@echo off
cd /d "%~dp0"
set LOCAL_MODE=true
set PYTHONIOENCODING=utf-8
start "" pythonw oracle_desktop.py
