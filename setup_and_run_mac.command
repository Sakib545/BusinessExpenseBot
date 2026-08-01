#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== Telegram Excel Filter Bot Setup ==="

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 পাওয়া যায়নি। আগে python.org থেকে Python 3 ইনস্টল করুন।"
  read -r -p "Enter চাপুন..."
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo
  read -r -s -p "BotFather-এর নতুন Bot Token paste করুন: " BOT_TOKEN
  echo
  if [ -z "$BOT_TOKEN" ]; then
    echo "Token খালি রাখা যাবে না।"
    read -r -p "Enter চাপুন..."
    exit 1
  fi
  printf 'BOT_TOKEN=%s\nMAX_FILE_SIZE_MB=20\n' "$BOT_TOKEN" > .env
  chmod 600 .env
fi

echo
echo "Bot চালু হচ্ছে। বন্ধ করতে Control+C চাপুন।"
python bot.py
