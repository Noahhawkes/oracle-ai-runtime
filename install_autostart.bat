@echo off
cd /d "%~dp0"
echo Registering ORACLE.AI auto-start in Windows Task Scheduler...
python core\autostart.py install
echo.
if %ERRORLEVEL%==0 (
    echo SUCCESS — ORACLE will now launch automatically at every Windows login.
) else (
    echo FAILED — see error above.
)
pause
