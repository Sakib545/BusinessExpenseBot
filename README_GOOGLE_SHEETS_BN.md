# Google Sheets Setup

Sheet-এর প্রথম row bot নিজে তৈরি করবে:

`Date | Time | Product | Qty | COD | Phone`

Railway Variables-এ যোগ করুন:

- `GOOGLE_SHEET_ID` — Google Sheet URL-এর `/d/` এবং `/edit`-এর মাঝের অংশ
- `GOOGLE_WORKSHEET=Orders`
- `GOOGLE_CREDENTIALS_JSON` — Service Account JSON-এর সম্পূর্ণ content এক লাইনে

Google Sheet-টি Service Account-এর `client_email`-এর সঙ্গে **Editor** হিসেবে Share করতে হবে।

নতুন CSV import করলে কেবল Database-এ নতুনভাবে insert হওয়া order Sheet-এ যাবে। Duplicate order যাবে না। Google Sheets API ব্যর্থ হলেও SQLite import ও export বন্ধ হবে না।

**Time কলাম:** বর্তমান version-এ CSV import/sync-এর Asia/Dhaka সময় লেখা হয়। Date কলাম order-এর আসল `order_date` ব্যবহার করে।
