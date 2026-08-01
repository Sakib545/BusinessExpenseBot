#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d ".venv" ] || [ ! -f ".env" ]; then
  echo "আগে setup_and_run_mac.command চালান।"
  read -r -p "Enter চাপুন..."
  exit 1
fi
source .venv/bin/activate
python bot.py
