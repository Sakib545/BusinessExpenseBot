# Business Expense Telegram Bot

দুইজন নির্দিষ্ট ব্যবহারকারীর পাঠানো ব্যবসার খরচ Google Sheet-এ সংরক্ষণ করে।

## সুবিধা

- শুধু `ALLOWED_USER_IDS`-এ থাকা ঠিক ২টি Telegram User ID ব্যবহার করতে পারবে
- ইংরেজি ও বাংলা সংখ্যা বোঝে
- প্রতিটি খরচ বাংলাদেশের বর্তমান তারিখসহ সেভ হয়
- `/today`, `/month`, `/summary` রিপোর্ট
- Google Sheet না থাকলে নির্ধারিত worksheet নিজে তৈরি করে
- Render Background Worker হিসেবে deploy করা যায়

## ফাইল

- `bot.py` — Telegram handler ও রিপোর্ট
- `config.py` — environment configuration
- `expense_parser.py` — মেসেজ থেকে amount/category বের করে
- `sheets.py` — Google Sheets read/write
- `render.yaml` — Render Blueprint
- `.env.example` — environment variable নমুনা

## ১. Telegram Bot তৈরি

1. Telegram-এ `@BotFather` খুলুন।
2. `/newbot` পাঠান।
3. Bot-এর নাম ও username দিন।
4. BotFather যে token দেবে সেটি কপি করুন—এটাই `BOT_TOKEN`।
5. দুই ব্যবহারকারী `@userinfobot`-এ `/start` দিয়ে নিজেদের numeric ID নিন।
6. ID দুটি comma দিয়ে লিখবেন: `111111111,222222222`।

## ২. Google Cloud ও Service Account

1. [Google Cloud Console](https://console.cloud.google.com/) খুলুন।
2. নতুন Project তৈরি করুন বা পুরোনো Project নির্বাচন করুন।
3. **APIs & Services → Library** থেকে এগুলো Enable করুন:
   - Google Sheets API
   - Google Drive API
4. **IAM & Admin → Service Accounts → Create service account** খুলুন।
5. একটি Service Account তৈরি করুন; আলাদা Project role দেওয়া জরুরি নয়।
6. Service Account খুলে **Keys → Add key → Create new key → JSON** নির্বাচন করুন।
7. JSON credentials ফাইলটি নিরাপদে রাখুন; GitHub-এ upload করবেন না।
8. JSON-এর `client_email` কপি করুন।

## ৩. Google Sheet তৈরি

1. নতুন Google Sheet তৈরি করুন।
2. Sheet-এর tab-এর নাম `Expenses` রাখুন।
3. প্রথম row খালি রাখতে পারেন—Bot নিজে `Date`, `Category`, `Amount` header বসাবে।
4. **Share** চাপুন এবং Service Account-এর `client_email`-কে **Editor** access দিন।
5. Sheet URL এমন হবে:

   `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`

   `/d/` এবং `/edit`-এর মাঝের অংশটি `SPREADSHEET_ID`।

## ৪. লোকাল কম্পিউটারে চালানো

Python 3.10 বা নতুন সংস্করণ ব্যবহার করুন।

```bash
python -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Package install:

```bash
pip install -r requirements.txt
```

`.env.example` কপি করে `.env` নাম দিন। তারপর:

```env
BOT_TOKEN=BotFather_token
ALLOWED_USER_IDS=প্রথম_ID,দ্বিতীয়_ID
SPREADSHEET_ID=Google_Sheet_ID
WORKSHEET_NAME=Expenses
TIMEZONE=Asia/Dhaka
GOOGLE_CREDENTIALS_JSON=সম্পূর্ণ_JSON_এক_লাইনে
```

JSON-টি এক লাইনে বানানোর সহজ উপায়:

macOS/Linux:

```bash
python -c 'import json; print(json.dumps(json.load(open("credentials.json"))))'
```

Windows PowerShell:

```powershell
python -c "import json; print(json.dumps(json.load(open('credentials.json'))))"
```

Bot চালান:

```bash
python bot.py
```

## ৫. Render.com deployment

### GitHub-এ push

নতুন private GitHub repository তৈরি করে এই project-এর সব ফাইল push করুন। `.env`
এবং Google credentials JSON ফাইল কখনো commit করবেন না।

### Background Worker তৈরি

1. [Render Dashboard](https://dashboard.render.com/) → **New → Background Worker**।
2. GitHub repository connect করুন।
3. Runtime: `Python`
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python bot.py`
6. Instance plan নির্বাচন করুন।
7. Environment-এ যোগ করুন:

| Key | Value |
|---|---|
| `BOT_TOKEN` | BotFather token |
| `ALLOWED_USER_IDS` | `111111111,222222222` |
| `SPREADSHEET_ID` | Sheet ID |
| `WORKSHEET_NAME` | `Expenses` |
| `TIMEZONE` | `Asia/Dhaka` |
| `GOOGLE_CREDENTIALS_JSON` | এক লাইনের সম্পূর্ণ JSON |

8. **Create Background Worker** চাপুন।
9. Log-এ `Business Expense Bot started` দেখলে Bot চালু।

`render.yaml` দিয়ে Blueprint deployment-ও করা যাবে; secret values Render
Dashboard-এ নিজে দিতে হবে।

## ব্যবহার

```text
10000 তেলের টাকা
৫০০০ পলির টাকা
3,000 বেতন
```

Bot Sheet-এ এমন row যোগ করবে:

| Date | Category | Amount |
|---|---|---:|
| 2026-07-30 | তেলের টাকা | 10000 |

কমান্ড:

- `/today` — আজকের category-wise হিসাব ও মোট
- `/month` — চলতি মাসের category-wise হিসাব ও মোট
- `/summary` — Sheet-এর সব সময়ের category-wise হিসাব ও মোট

## সমস্যার সমাধান

- `SpreadsheetNotFound`: Sheet ID ভুল অথবা Service Account email-কে Editor করা হয়নি।
- `GOOGLE_CREDENTIALS_JSON সঠিক JSON নয়`: JSON এক লাইনে ঠিকভাবে paste করুন।
- Bot উত্তর দেয় না: Render Worker log ও `BOT_TOKEN` পরীক্ষা করুন।
- অনুমতি নেই: `ALLOWED_USER_IDS`-এ Telegram numeric ID দুটি ঠিক আছে কি না দেখুন।
- Header error: প্রথম row ঠিক `Date`, `Category`, `Amount` করুন।

## নিরাপত্তা

- Repository private রাখুন।
- `.env` বা credentials JSON commit করবেন না।
- Telegram token প্রকাশ হলে BotFather থেকে সঙ্গে সঙ্গে revoke করুন।
- Google key প্রকাশ হলে Cloud Console থেকে key delete করে নতুন key বানান।
