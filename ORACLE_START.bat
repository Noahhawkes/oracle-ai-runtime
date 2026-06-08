@echo off
title ORACLE Resident Runtime
cd /d "%~dp0"
echo.
echo  ==========================================
echo   ORACLE.AI -- Resident Runtime Starting
echo  ==========================================
echo.
echo  Cycles every 30 min. Presence window on each cycle.
echo  Press Ctrl+C to stop gracefully.
echo.
python core/resident_runtime.py --interval 30
pause
