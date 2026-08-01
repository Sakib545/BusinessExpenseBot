@echo off
cd /d "%~dp0"
title Telegram Excel Filter Bot
if not exist ".venv\Scripts\python.exe" (
  echo আগে setup_and_run_windows.bat চালান।
  pause
  exit /b 1
)
if not exist ".env" (
  echo আগে setup_and_run_windows.bat চালান।
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python bot.py
pause
