@echo off
cd /d "%~dp0"
setlocal

:: ── ORACLE Desktop Launcher ───────────────────────────────────────────────
:: Double-click to start ORACLE in the browser.
:: If the server is already running, just open the tab.
:: Errors are logged to Logs\oracle_startup.log

set PORT=7777
set URL=http://localhost:%PORT%
set LOGFILE=%~dp0Logs\oracle_startup.log

:: Write timestamped startup record
echo. >> "%LOGFILE%"
echo [%DATE% %TIME%] oracle_desktop.bat launched >> "%LOGFILE%"

:: Check if server is already up
curl -s --connect-timeout 1 --max-time 1 "%URL%/api/mode" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] Server already running on port %PORT% -- opening browser >> "%LOGFILE%"
    goto :open_browser
)

:: Start server — redirect stderr to startup log so errors are captured
echo [%DATE% %TIME%] Starting oracle_server.py on port %PORT% >> "%LOGFILE%"
set PYTHONIOENCODING=utf-8
start "" /B pythonw oracle_server.py --port %PORT% 2>> "%LOGFILE%"

:: Poll until ready (up to 15 seconds)
set tries=0
:wait_loop
timeout /t 1 /nobreak >nul
curl -s --connect-timeout 1 --max-time 1 "%URL%/api/mode" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] Server ready after %tries%s >> "%LOGFILE%"
    goto :open_browser
)
set /a tries+=1
if %tries% LSS 15 goto :wait_loop

:: Server never came up — log the failure and open anyway so the error is visible
echo [%DATE% %TIME%] ERROR: Server did not respond after 15s. Check %LOGFILE% >> "%LOGFILE%"
echo.
echo  ORACLE failed to start. Check: %LOGFILE%
echo  Press any key to open browser anyway, or close this window to abort.
pause >nul

:open_browser
echo [%DATE% %TIME%] Opening %URL% >> "%LOGFILE%"
start "" "%URL%"
endlocal
