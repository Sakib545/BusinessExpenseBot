#!/bin/bash
cd "$(dirname "$0")"
if [ -f bot.pid ] && kill -0 "$(cat bot.pid)" 2>/dev/null; then
  kill "$(cat bot.pid)"
  rm -f bot.pid
  echo "Bot বন্ধ হয়েছে।"
else
  rm -f bot.pid
  echo "চলমান background bot পাওয়া যায়নি।"
fi
read -r -p "Enter চাপুন..."
