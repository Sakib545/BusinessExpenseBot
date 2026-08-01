"""Google Sheets live mirror for Smart Product Accounts Bot v2.0.

SQLite remains the source of truth. Sheet failures are logged and never stop imports.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

HEADERS = ["Date", "Time", "Product", "Qty", "COD", "Phone", "Order Key"]
VISIBLE_COLUMNS = 6
TAB_ALL = "All Orders"
TAB_PAIN = "Pain Oil"
TAB_HAIR_100 = "Hair Oil 100ml"
TAB_HAIR_200 = "Hair Oil 200ml"
TAB_MIXED = "Mixed Orders"
TAB_UNKNOWN = "Unknown"
ALL_TABS = [TAB_ALL, TAB_PAIN, TAB_HAIR_100, TAB_HAIR_200, TAB_MIXED, TAB_UNKNOWN]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _credentials_info() -> dict[str, Any]:
    raw = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON is missing")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON is not valid JSON") from exc


def enabled() -> bool:
    return bool(os.getenv("GOOGLE_SHEET_ID", "").strip() and os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip())


def _spreadsheet() -> gspread.Spreadsheet:
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID is missing")
    credentials = Credentials.from_service_account_info(_credentials_info(), scopes=SCOPES)
    return gspread.authorize(credentials).open_by_key(sheet_id)


def _ensure_worksheet(book: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    try:
        ws = book.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=title, rows=1000, cols=len(HEADERS))

    current = ws.row_values(1)
    if current[: len(HEADERS)] != HEADERS:
        ws.update(range_name="A1:G1", values=[HEADERS])
    try:
        ws.freeze(rows=1)
        ws.hide_columns(6, 7)  # hide G (0-based start, end-exclusive)
        ws.format("A1:G1", {"textFormat": {"bold": True}, "horizontalAlignment": "CENTER"})
    except Exception:
        logging.exception("Could not apply worksheet formatting: %s", title)
    return ws



def _retry(operation, *args, attempts: int = 3, **kwargs):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return operation(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt)
    assert last_error is not None
    raise last_error

def setup_tabs() -> None:
    if not enabled():
        return
    book = _spreadsheet()
    for title in ALL_TABS:
        _ensure_worksheet(book, title)


def _order_key(row: dict[str, Any]) -> str:
    consignment = str(row.get("consignment") or "").strip()
    merchant_id = str(row.get("merchant_id") or "").strip()
    if consignment:
        return f"C:{consignment.casefold()}"
    if merchant_id:
        return f"M:{merchant_id.casefold()}"
    return ""


def _qty(row: dict[str, Any]) -> int:
    try:
        value = int(row.get("total_quantity") or 0)
        if value > 0:
            return value
    except (TypeError, ValueError):
        pass
    description = str(row.get("description") or "")
    matches = re.findall(r"\bx\s*(\d+)\s*(?:qty|pcs?|pieces?)?\b", description, flags=re.I)
    return sum(max(1, int(v)) for v in matches) if matches else 1


def _is_mixed(row: dict[str, Any]) -> bool:
    product = str(row.get("product") or "").strip().casefold()
    description = str(row.get("description") or "")
    return product == "mixed orders" or "||" in description or _qty(row) > 1 or not bool(row.get("export_eligible", True))


def _hair_tab(row: dict[str, Any]) -> str:
    text = f"{row.get('product', '')} {row.get('description', '')}".casefold()
    if re.search(r"\b200\s*ml\b", text):
        return TAB_HAIR_200
    return TAB_HAIR_100


def target_tabs(row: dict[str, Any]) -> list[str]:
    if _is_mixed(row):
        return [TAB_ALL, TAB_MIXED]
    product = str(row.get("product") or "").strip().casefold()
    if product == "pain oil":
        return [TAB_ALL, TAB_PAIN]
    if "hair oil" in product:
        return [TAB_ALL, _hair_tab(row)]
    return [TAB_ALL, TAB_UNKNOWN]


def _sheet_row(row: dict[str, Any]) -> list[Any]:
    imported = str(row.get("imported_at") or "").strip()
    try:
        dt = datetime.fromisoformat(imported) if imported else datetime.now(ZoneInfo("Asia/Dhaka"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Dhaka"))
        time_value = dt.astimezone(ZoneInfo("Asia/Dhaka")).strftime("%H:%M:%S")
    except ValueError:
        time_value = datetime.now(ZoneInfo("Asia/Dhaka")).strftime("%H:%M:%S")
    return [
        str(row.get("order_date") or ""),
        time_value,
        str(row.get("product") or "Unknown Product"),
        _qty(row),
        float(row.get("cod") or 0),
        str(row.get("phone") or ""),
        _order_key(row),
    ]


def append_orders(rows: Iterable[dict[str, Any]]) -> int:
    rows = [dict(row) for row in rows if _order_key(dict(row))]
    if not rows or not enabled():
        return 0
    book = _retry(_spreadsheet)
    grouped: dict[str, list[list[Any]]] = {title: [] for title in ALL_TABS}
    for row in rows:
        values = _sheet_row(row)
        for title in target_tabs(row):
            grouped[title].append(values)

    synced_keys: set[str] = set()
    for title, values in grouped.items():
        if not values:
            continue
        ws = _retry(_ensure_worksheet, book, title)
        existing = {str(v).strip().casefold() for v in _retry(ws.col_values, 7)[1:] if str(v).strip()}
        fresh = [v for v in values if str(v[6]).strip().casefold() not in existing]
        if fresh:
            _retry(ws.append_rows, fresh, value_input_option="USER_ENTERED")
            synced_keys.update(str(v[6]).strip().casefold() for v in fresh)
    return len({_order_key(row).casefold() for row in rows if _order_key(row)})


def delete_orders(rows: Iterable[dict[str, Any]]) -> int:
    keys = {_order_key(dict(row)).strip().casefold() for row in rows}
    keys.discard("")
    if not keys or not enabled():
        return 0
    book = _retry(_spreadsheet)
    deleted = 0
    for title in ALL_TABS:
        ws = _retry(_ensure_worksheet, book, title)
        key_values = _retry(ws.col_values, 7)
        indexes = [
            index for index, value in enumerate(key_values, start=1)
            if index > 1 and str(value).strip().casefold() in keys
        ]
        for index in reversed(indexes):
            _retry(ws.delete_rows, index)
            deleted += 1
    return deleted


def replace_all(rows: Iterable[dict[str, Any]]) -> int:
    rows = [dict(row) for row in rows]
    if not enabled():
        return 0
    book = _retry(_spreadsheet)
    for title in ALL_TABS:
        ws = _retry(_ensure_worksheet, book, title)
        _retry(ws.clear)
        _retry(ws.update, range_name="A1:G1", values=[HEADERS])
    return append_orders(rows)

