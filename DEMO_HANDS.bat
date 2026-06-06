@echo off
title SOV1.AI - Live Hands Demo
echo.
echo  SOV1.AI is about to take control.
echo  WATCH YOUR SCREEN - Notepad will open and type on its own.
echo.
echo  (To abort anytime: slam your mouse into a screen corner.)
echo.
timeout /t 3
cd /d "%~dp0"
python core\computer_control.py
echo.
echo  ============================================
echo   Demo done. Did Notepad open and type itself?
echo  ============================================
pause
