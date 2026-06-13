@echo off
cd /d "%~dp0"
setlocal

:: ── ORACLE Desktop Launcher ───────────────────────────────────────────────
:: Double-click to start ORACLE in the browser.
:: If the server is already running, just open the tab.

set PORT=7777
set URL=http://localhost:%PORT%

:: Check if server is already up
curl -s --connect-timeout 1 --max-time 1 "%URL%/api/mode" >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :open_browser

:: Start server silently in background
set PYTHONIOENCODING=utf-8
start "" /B pythonw oracle_server.py --port %PORT%

:: Poll until ready (up to 12 seconds)
set tries=0
:wait_loop
timeout /t 1 /nobreak >nul
curl -s --connect-timeout 1 --max-time 1 "%URL%/api/mode" >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :open_browser
set /a tries+=1
if %tries% LSS 12 goto :wait_loop

:open_browser
start "" "%URL%"
endlocal
