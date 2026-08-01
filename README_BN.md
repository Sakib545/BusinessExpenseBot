# Smart Product & Date-wise Accounts Telegram Bot v3

এই ভার্সনে CSV/XLSX আপলোড করলে `Order description` দেখে Product শনাক্ত করে আলাদা Excel বানায় এবং সব অর্ডারের হিসাব SQLite Database-এ তারিখ অনুযায়ী রাখে।

## Product শনাক্তকরণ

- `HAIR OIL 100ML` / `HAIR OIL` → **Hair Oil**
- `বুরাক নাইজেলা ম্যাসাজ অয়েল - 200ml` / `Buraq Nigella Massage Oil` → **Pain Oil**
- না মিললে → **Unknown Product**

Output filename:

- `Hair Oil - 39 Orders.xlsx`
- `Pain Oil - 600 Orders.xlsx`

## হিসাবের কমান্ড

- `/today` — আজকের হিসাব
- `/yesterday` — গতকালের হিসাব
- `/date 2026-07-27` — নির্দিষ্ট দিনের হিসাব
- `/month` — চলতি মাস
- `/summary` — শুরু থেকে মোট হিসাব
- `/hair` — Hair Oil মোট
- `/pain` — Pain Oil মোট
- `/find CONSIGNMENT` — Consignment, ID অথবা Number দিয়ে খোঁজা
- `/export` — সব হিসাবের Excel রিপোর্ট

## Database

সব হিসাব `bot_data.db` ফাইলে থাকে। Bot folder delete করলে এই হিসাবও মুছে যাবে, তাই নিয়মিত backup রাখুন। একই Consignment আবার আপলোড হলে Database-এ দ্বিতীয়বার যোগ হবে না।

## চালু করার নিয়ম

1. `.env.example` কপি করে `.env` বানান।
2. নতুন Telegram Bot token বসান:

```env
BOT_TOKEN=YOUR_NEW_TOKEN
MAX_FILE_SIZE_MB=20
```

3. Windows: প্রথমবার `setup_and_run_windows.bat`, পরে `run_windows.bat`।
4. Mac: প্রথমবার `setup_and_run_mac.command`, পরে `run_mac.command`।

## নতুন Product যোগ

`products.json` খুলে Product name ও description keyword যোগ করুন। Python code বদলাতে হবে না।
