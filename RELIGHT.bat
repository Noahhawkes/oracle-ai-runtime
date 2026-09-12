@echo off
title ORACLE RELIGHT
cd /d "%~dp0"
echo.
echo  ============================================
echo    ORACLE RELIGHT - restart the real engine
echo  ============================================
echo.
echo  Closing browsers does nothing. THIS restarts the
echo  windowless Python process that actually serves 7781,
echo  so she loads the new code (durable threads, your Laws,
echo  the recall fix that knows Ashley is your wife).
echo.

echo  [1/3] Stopping the stale ORACLE on port 7781...
set "KILLED="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":7781" ^| findstr LISTENING') do (
    echo        killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
    set "KILLED=1"
)
if not defined KILLED echo        (nothing was listening - starting fresh)
timeout /t 2 /nobreak >nul

echo  [2/3] Starting ORACLE fresh on the new code...
set PYTHONIOENCODING=utf-8
set "PYW=%LOCALAPPDATA%\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" /B "%PYW%" oracle_server.py --port 7781
echo        launched. giving her ~12s to boot...
timeout /t 12 /nobreak >nul

echo  [3/3] Proving she is live on the new code...
python tools\relight_prove.py
echo.
echo  If receipt 1 is GREEN, she is relit. Then run these three,
echo  one at a time, to make it all real:
echo     python tools\seed_people.py --apply
echo     python tools\backfill_threads.py --apply
echo     python tools\ingest_everything.py --apply
echo.
echo  Leave this window open. Press a key to close it.
pause >nul
