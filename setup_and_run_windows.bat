@echo off
setlocal
cd /d "%~dp0"
title Telegram Excel Filter Bot Setup

echo === Telegram Excel Filter Bot Setup ===
where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py"
) else (
  where python >nul 2>nul
  if not %errorlevel%==0 (
    echo Python পাওয়া যায়নি। python.org থেকে Python ইনস্টল করে আবার চালান।
    pause
    exit /b 1
  )
  set "PY=python"
)

if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist ".env" (
  echo.
  set /p "BOT_TOKEN=BotFather-এর নতুন Bot Token paste করুন: "
  if "%BOT_TOKEN%"=="" (
    echo Token খালি রাখা যাবে না।
    pause
    exit /b 1
  )
  >.env echo BOT_TOKEN=%BOT_TOKEN%
  >>.env echo MAX_FILE_SIZE_MB=20
)

echo.
echo Bot চালু হচ্ছে। বন্ধ করতে Ctrl+C চাপুন।
python bot.py
pause
