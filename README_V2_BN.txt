SMART PRODUCT ACCOUNTS BOT v2.0

Google Spreadsheet tabs automatically created:
- All Orders
- Pain Oil
- Hair Oil 100ml
- Hair Oil 200ml
- Mixed Orders
- Unknown

Visible columns:
Date | Time | Product | Qty | COD | Phone

A hidden G column (Order Key) is used only for exact delete sync.
Mixed rule:
- description contains ||, OR
- total Qty > 1, OR
- processor marks the row export-ineligible/mixed.

Import:
- SQLite first, then Google Sheets.
- Duplicate orders are not appended.

Delete import:
- SQLite rows are deleted.
- Matching rows are removed from All Orders and the product/mixed tab.

/resync:
- Clears all six tabs and rebuilds them from SQLite.

Railway variables:
DATA_DIR=/data
GOOGLE_SHEET_ID=1e8Ev_j2DPNI8rUAVVtZYCl_WPe9P_WrAejfxZjA-d7Y
GOOGLE_CREDENTIALS_JSON=<new complete service account JSON>

Share the spreadsheet with the service account client_email as Editor.
Never upload the service account JSON to GitHub.
