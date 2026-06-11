@echo off
:: ORACLE Heart Mode
:: No tools. No gates. Just Noah and ORACLE talking.
::
:: Double-click this file to start Heart Mode.
:: Type  quit  or press Ctrl-C to exit.

title ORACLE Heart Mode

:: Enable UTF-8 and ANSI colour support
chcp 65001 > nul
:: VirtualTerminalLevel enables ANSI on Windows 10+
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f > nul 2>&1

:: Move to the project root (same folder as this .bat file)
cd /d "%~dp0"

:: Activate venv if present, otherwise use system Python
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo   Starting ORACLE Heart Mode...
echo   (Ctrl-C or type  quit  to exit)
echo.

python core\oracle_heart.py

echo.
echo   Heart Mode ended. Window stays open so you can read any final message.
pause
