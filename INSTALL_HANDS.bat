@echo off
title SOV1.AI - Installing the Hands
echo.
echo  Installing computer control for SOV1.AI...
echo  (mouse, keyboard, screen, window control)
echo.
python -m pip install pyautogui mss pygetwindow
echo.
echo  ============================================
echo   DONE. The hands are installed.
echo   Go back to Claude and say: "ready"
echo  ============================================
echo.
pause
