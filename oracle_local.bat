@echo off
title ORACLE.AI — LOCAL MODE
cd /d "%~dp0"
set LOCAL_MODE=true
echo.
echo Starting ORACLE.AI in local mode (Ollama / qwen2.5:7b)...
echo Make sure Ollama is running before continuing.
echo.
python core/oracle.py
echo.
if %ERRORLEVEL% neq 0 (
    echo.
    echo ORACLE exited with an error. Read the message above.
    echo Common fixes:
    echo   - Make sure Ollama is running: start the Ollama app or run "ollama serve"
    echo   - Make sure the model is pulled: ollama pull qwen2.5:7b
    echo   - Make sure Python is installed and in your PATH
)
pause
