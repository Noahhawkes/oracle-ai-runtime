@echo off
REM ORACLE Operator Home - desktop double-click launcher (v1).
REM Detects the current runtime and routes you there, never the stale 7777 copy.
REM The Desktop "ORACLE" shortcut points here. (Existing ORACLE.bat = CLI, untouched.)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ORACLE.ps1" %*
