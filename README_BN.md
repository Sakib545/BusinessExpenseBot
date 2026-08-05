# Business Expense Custom Category — SAFE UPDATE

## এখন কাজ করবে

- `500 খরচ`
- `300 খাবার`
- `500 khoroch`
- `500 খরচ 300 খাবার`
- একাধিক line:
  ```
  500 খরচ
  300 খাবার
  120 চা
  ```

Custom category সরাসরি `All Expenses` Sheet-এ save হবে। Today, Month, Summary, Excel/PDF এবং Central Sync-এও থাকবে।

শুধু amount পাঠালে আগের category button একই থাকবে।

## Replace করুন

- `bot.py`
- `expense_parser.py`

## কখনো Replace/Delete করবেন না

- `.env`
- Google credentials
- Railway Variables
- কোনো database
- `/data`
- Railway Volume
- backup

Risk: SAFE INCREMENTAL UPDATE
