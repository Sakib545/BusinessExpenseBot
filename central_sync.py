from __future__ import annotations
import json, os, time
from datetime import datetime
from typing import Any
import gspread
from google.oauth2.service_account import Credentials

SCOPES=["https://www.googleapis.com/auth/spreadsheets"]

def enabled() -> bool:
    return bool(os.getenv("CENTRAL_SHEET_ID", "").strip() and (os.getenv("CENTRAL_GOOGLE_CREDENTIALS_JSON", "").strip() or os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()))

def _book():
    sid=os.getenv("CENTRAL_SHEET_ID", "").strip()
    raw=os.getenv("CENTRAL_GOOGLE_CREDENTIALS_JSON", "").strip() or os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    if not sid or not raw: raise RuntimeError("CENTRAL_SHEET_ID / credentials missing")
    info=json.loads(raw)
    creds=Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(sid)

def _retry(fn,*args,attempts=3,**kwargs):
    last=None
    for i in range(attempts):
        try: return fn(*args,**kwargs)
        except Exception as e:
            last=e
            if i+1<attempts: time.sleep(i+1)
    raise last

def _ws(title:str, headers:list[str]):
    book=_retry(_book)
    try: ws=book.worksheet(title)
    except gspread.WorksheetNotFound: ws=book.add_worksheet(title=title, rows=2000, cols=max(10,len(headers)))
    if ws.row_values(1)[:len(headers)] != headers:
        ws.clear(); ws.update(range_name=f"A1:{chr(64+len(headers))}1", values=[headers])
    try: ws.freeze(rows=1)
    except Exception: pass
    return ws

def replace_tab(title:str, headers:list[str], rows:list[list[Any]]) -> int:
    if not enabled(): return 0
    ws=_ws(title,headers)
    ws.clear(); ws.update(range_name=f"A1:{chr(64+len(headers))}1", values=[headers])
    if rows: ws.append_rows(rows, value_input_option="USER_ENTERED")
    _touch(title, len(rows))
    return len(rows)

def _touch(source:str,count:int):
    headers=["Source","Last Sync","Rows"]
    ws=_ws("Sync_Status",headers)
    values=ws.get_all_values()
    now=datetime.now().isoformat(timespec="seconds")
    found=None
    for idx,row in enumerate(values[1:],start=2):
        if row and row[0]==source: found=idx; break
    if found: ws.update(range_name=f"A{found}:C{found}", values=[[source,now,count]])
    else: ws.append_row([source,now,count], value_input_option="USER_ENTERED")

def read_tab(title:str) -> list[dict[str,Any]]:
    if not enabled(): return []
    try: return _book().worksheet(title).get_all_records()
    except gspread.WorksheetNotFound: return []

HEADERS=["Source ID","Date","Category","Amount","Updated At"]
def sync_expense_snapshot(store) -> dict[str,Any]:
    rows=[]
    for r in store.get_all():
        rows.append([f"EXP-{r['row_number']}",r['date'].isoformat(),r['category'],float(r['amount'] or 0),datetime.now().isoformat(timespec='seconds')])
    return {"synced":replace_tab("Business_Expenses",HEADERS,rows)}
