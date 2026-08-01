# Pathao Auto Sync Setup

Railway/Render Variables-এ নিচের values বসান। Secret কখনো GitHub বা Telegram-এ দেবেন না।

```env
PATHAO_CLIENT_ID=your_client_id
PATHAO_CLIENT_SECRET=your_client_secret
PATHAO_USERNAME=merchant_email
PATHAO_PASSWORD=merchant_password
PATHAO_AUTO_SYNC=true
PATHAO_SYNC_MINUTES=15
PATHAO_SYNC_LIMIT=300
```

যদি Pathao permanent access token দেয়, username/password-এর বদলে এটি ব্যবহার করা যায়:

```env
PATHAO_ACCESS_TOKEN=your_access_token
```

Default API configuration:

```env
PATHAO_BASE_URL=https://api-hermes.pathao.com/aladdin/api/v1
PATHAO_TOKEN_ENDPOINT=/issue-token
PATHAO_ORDER_INFO_ENDPOINT=/orders/{consignment_id}/info
PATHAO_HTTP_TIMEOUT=25
```

তোমার Pathao panel-এর API documentation-এ endpoint আলাদা থাকলে শুধু Variables-এর endpoint values বদলাবে; code বদলাতে হবে না।

## ব্যবহার

- Telegram menu থেকে `🔄 Pathao Sync` চাপলে সঙ্গে সঙ্গে sync হবে।
- `↩️ Return Report` চাপলে Total COD, Return COD ও Net COD দেখা যাবে।
- `/pathao_sync` এবং `/returns` command-ও কাজ করবে।
- `PATHAO_AUTO_SYNC=true` হলে নির্ধারিত সময় পরপর automatic sync হবে।

## হিসাব

- Returned parcel-এর exact imported COD `Return COD`-এ যোগ হবে।
- `Net COD = Total COD - Return COD`
- Consignment ID দিয়ে একই return দ্বিতীয়বার minus হবে না।
- Product নাম imported CSV/Excel order থেকেই নেওয়া হবে।
