#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d ".venv" ] || [ ! -f ".env" ]; then
  echo "আগে setup_and_run_mac.command চালান।"
  read -r -p "Enter চাপুন..."
  exit 1
fi
if [ -f bot.pid ] && kill -0 "$(cat bot.pid)" 2>/dev/null; then
  echo "Bot ইতিমধ্যে চলছে। PID: $(cat bot.pid)"
else
  source .venv/bin/activate
  nohup python bot.py >> bot.log 2>&1 &
  echo $! > bot.pid
  echo "Bot background-এ চালু হয়েছে। PID: $(cat bot.pid)"
  echo "Log: bot.log"
fi
read -r -p "Enter চাপুন..."
