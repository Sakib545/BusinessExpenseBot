import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
import os
from typing import Any, Iterable

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "bot_data.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(r["name"]) for r in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_legacy_orders(conn: sqlite3.Connection) -> None:
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
    if not exists:
        return
    cols = _columns(conn, "orders")
    # V5 stable has an integer id and batch_id. Legacy versions used consignment as PK.
    if "id" in cols and "batch_id" in cols:
        return
    conn.execute("ALTER TABLE orders RENAME TO orders_legacy")
    conn.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consignment TEXT,
            merchant_id TEXT,
            phone TEXT,
            product TEXT NOT NULL,
            cod REAL NOT NULL DEFAULT 0,
            order_date TEXT NOT NULL,
            description TEXT,
            source_file TEXT,
            batch_id TEXT,
            imported_at TEXT NOT NULL
        )
        """
    )
    legacy_cols = _columns(conn, "orders_legacy")
    def expr(name: str, fallback: str = "NULL") -> str:
        return name if name in legacy_cols else fallback
    conn.execute(
        f"""
        INSERT INTO orders (
            consignment, merchant_id, phone, product, cod, order_date,
            description, source_file, batch_id, imported_at
        )
        SELECT
            {expr('consignment')}, {expr('merchant_id')}, {expr('phone')},
            COALESCE({expr('product', "'Unknown Product'")}, 'Unknown Product'),
            COALESCE({expr('cod', '0')}, 0),
            COALESCE({expr('order_date', "date('now')")}, date('now')),
            {expr('description')}, {expr('source_file')}, NULL,
            COALESCE({expr('imported_at', "datetime('now')")}, datetime('now'))
        FROM orders_legacy
        """
    )
    conn.execute("DROP TABLE orders_legacy")


def init_db() -> None:
    with connect() as conn:
        _migrate_legacy_orders(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consignment TEXT,
                merchant_id TEXT,
                phone TEXT,
                product TEXT NOT NULL,
                cod REAL NOT NULL DEFAULT 0,
                order_date TEXT NOT NULL,
                description TEXT,
                source_file TEXT,
                batch_id TEXT,
                imported_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_consignment ON orders(lower(consignment)) WHERE consignment IS NOT NULL AND trim(consignment) != ''")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_merchant ON orders(lower(merchant_id)) WHERE merchant_id IS NOT NULL AND trim(merchant_id) != ''")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_orders_batch ON orders(batch_id)")
        order_cols = _columns(conn, "orders")
        order_additions = {
            "courier_status": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
            "courier_cod": "REAL",
            "courier_synced_at": "TEXT",
            "returned_at": "TEXT",
            "delivered_at": "TEXT",
            "courier_raw": "TEXT",
        }
        for name, definition in order_additions.items():
            if name not in order_cols:
                conn.execute(f"ALTER TABLE orders ADD COLUMN {name} {definition}")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_orders_courier_status ON orders(courier_status)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT UNIQUE NOT NULL,
                source_file TEXT NOT NULL,
                total_rows INTEGER NOT NULL DEFAULT 0,
                inserted_rows INTEGER NOT NULL DEFAULT 0,
                duplicate_rows INTEGER NOT NULL DEFAULT 0,
                invalid_rows INTEGER NOT NULL DEFAULT 0,
                added_cod REAL NOT NULL DEFAULT 0,
                duplicate_cod REAL NOT NULL DEFAULT 0,
                export_files TEXT,
                imported_at TEXT NOT NULL
            )
            """
        )
        # Add missing columns when upgrading a partially updated database.
        ih_cols = _columns(conn, "import_history")
        additions = {
            "batch_id": "TEXT",
            "added_cod": "REAL NOT NULL DEFAULT 0",
            "duplicate_cod": "REAL NOT NULL DEFAULT 0",
            "export_files": "TEXT",
        }
        for name, definition in additions.items():
            if name not in ih_cols:
                conn.execute(f"ALTER TABLE import_history ADD COLUMN {name} {definition}")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_import_batch ON import_history(batch_id) WHERE batch_id IS NOT NULL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS duplicate_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consignment TEXT,
                merchant_id TEXT,
                phone TEXT,
                product TEXT,
                cod REAL NOT NULL DEFAULT 0,
                order_date TEXT,
                description TEXT,
                original_file TEXT,
                duplicate_file TEXT,
                duplicate_reason TEXT NOT NULL,
                batch_id TEXT,
                duplicate_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS ix_duplicate_batch ON duplicate_history(batch_id)")


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _find_duplicate(conn: sqlite3.Connection, consignment: str, merchant_id: str) -> sqlite3.Row | None:
    if consignment:
        row = conn.execute(
            "SELECT * FROM orders WHERE lower(consignment)=lower(?) LIMIT 1",
            (consignment,),
        ).fetchone()
        if row:
            return row
    if merchant_id:
        row = conn.execute(
            "SELECT * FROM orders WHERE lower(merchant_id)=lower(?) LIMIT 1",
            (merchant_id,),
        ).fetchone()
        if row:
            return row
    return None


def insert_orders_with_results(rows: Iterable[dict[str, Any]], batch_id: str = "") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    init_db()
    inserted: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        for raw in rows:
            row = dict(raw)
            consignment = clean_value(row.get("consignment"))
            merchant_id = clean_value(row.get("merchant_id"))
            row.update({
                "consignment": consignment,
                "merchant_id": merchant_id,
                "phone": clean_value(row.get("phone")),
                "product": clean_value(row.get("product")) or "Unknown Product",
                "order_date": clean_value(row.get("order_date")) or date.today().isoformat(),
                "description": clean_value(row.get("description")),
                "source_file": clean_value(row.get("source_file")),
                "batch_id": batch_id,
            })
            try:
                row["cod"] = float(row.get("cod") or 0)
            except (TypeError, ValueError):
                row["cod"] = 0.0
            if not consignment and not merchant_id:
                row["duplicate_reason"] = "Missing Consignment and Order ID"
                duplicates.append(row)
                continue
            original = _find_duplicate(conn, consignment, merchant_id)
            if original:
                if consignment and clean_value(original["consignment"]).casefold() == consignment.casefold():
                    reason = "Duplicate Consignment ID"
                else:
                    reason = "Duplicate Merchant Order ID"
                row["duplicate_reason"] = reason
                row["original_file"] = clean_value(original["source_file"])
                duplicates.append(row)
                conn.execute(
                    """
                    INSERT INTO duplicate_history (
                        consignment, merchant_id, phone, product, cod, order_date,
                        description, original_file, duplicate_file,
                        duplicate_reason, batch_id, duplicate_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (consignment, merchant_id, row["phone"], row["product"], row["cod"],
                     row["order_date"], row["description"], row["original_file"],
                     row["source_file"], reason, batch_id, now),
                )
                continue
            try:
                conn.execute(
                    """
                    INSERT INTO orders (
                        consignment, merchant_id, phone, product, cod, order_date,
                        description, source_file, batch_id, imported_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (consignment or None, merchant_id or None, row["phone"], row["product"],
                     row["cod"], row["order_date"], row["description"], row["source_file"],
                     batch_id, now),
                )
                inserted.append(row)
            except sqlite3.IntegrityError:
                row["duplicate_reason"] = "Duplicate Consignment or Merchant Order ID"
                duplicates.append(row)
    return inserted, duplicates


def insert_orders(rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    a, b = insert_orders_with_results(rows)
    return len(a), len(b)


def save_duplicate_rows(rows: Iterable[dict[str, Any]], batch_id: str, duplicate_file: str) -> None:
    init_db()
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        for raw in rows:
            row = dict(raw)
            conn.execute(
                """
                INSERT INTO duplicate_history (
                    consignment, merchant_id, phone, product, cod, order_date,
                    description, original_file, duplicate_file,
                    duplicate_reason, batch_id, duplicate_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (clean_value(row.get("consignment")), clean_value(row.get("merchant_id")),
                 clean_value(row.get("phone")), clean_value(row.get("product")),
                 float(row.get("cod") or 0), clean_value(row.get("order_date")),
                 clean_value(row.get("description")), clean_value(row.get("original_file")),
                 duplicate_file, clean_value(row.get("duplicate_reason")) or "Duplicate inside uploaded file",
                 batch_id, now),
            )


def log_import(batch_id: str, source_file: str, total_rows: int, inserted_rows: int, duplicate_rows: int, invalid_rows: int = 0, added_cod: float = 0, duplicate_cod: float = 0, export_files: str = "") -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO import_history (
                batch_id, source_file, total_rows, inserted_rows, duplicate_rows,
                invalid_rows, added_cod, duplicate_cod, export_files, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (batch_id, clean_value(source_file), int(total_rows), int(inserted_rows),
             int(duplicate_rows), int(invalid_rows), float(added_cod), float(duplicate_cod),
             clean_value(export_files), datetime.now().isoformat(timespec="seconds")),
        )


def report(start_date: str | None = None, end_date: str | None = None, product: str | None = None) -> list[sqlite3.Row]:
    init_db(); conditions=[]; params=[]
    if start_date: conditions.append("order_date >= ?"); params.append(start_date)
    if end_date: conditions.append("order_date <= ?"); params.append(end_date)
    if product: conditions.append("product = ?"); params.append(product)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with connect() as conn:
        return conn.execute(f"SELECT product, COUNT(*) orders, ROUND(COALESCE(SUM(cod),0),2) cod FROM orders{where} GROUP BY product ORDER BY product", params).fetchall()


def daily_report(start_date: str | None = None, end_date: str | None = None) -> list[sqlite3.Row]:
    init_db(); conditions=[]; params=[]
    if start_date: conditions.append("order_date >= ?"); params.append(start_date)
    if end_date: conditions.append("order_date <= ?"); params.append(end_date)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with connect() as conn:
        return conn.execute(f"SELECT order_date, product, COUNT(*) orders, ROUND(COALESCE(SUM(cod),0),2) cod FROM orders{where} GROUP BY order_date, product ORDER BY order_date DESC, product", params).fetchall()


def monthly_report(year: int | None = None, month: int | None = None) -> list[sqlite3.Row]:
    today=date.today(); year=int(year or today.year); month=int(month or today.month)
    start=date(year,month,1); next_month=date(year+1,1,1) if month==12 else date(year,month+1,1)
    return report(start.isoformat(), (next_month-timedelta(days=1)).isoformat())


def dashboard_summary() -> dict[str, Any]:
    init_db(); today=today_iso(); month_start=date.today().replace(day=1).isoformat()
    with connect() as conn:
        def agg(where="", params=()):
            return conn.execute(f"SELECT COUNT(*) orders, ROUND(COALESCE(SUM(cod),0),2) cod FROM orders {where}", params).fetchone()
        a=agg("WHERE order_date=?",(today,)); b=agg("WHERE order_date>=?",(month_start,)); c=agg()
        products=conn.execute("SELECT product, COUNT(*) orders, ROUND(COALESCE(SUM(cod),0),2) cod FROM orders GROUP BY product ORDER BY orders DESC, product").fetchall()
    return {"today_orders":int(a["orders"] or 0),"today_cod":float(a["cod"] or 0),"month_orders":int(b["orders"] or 0),"month_cod":float(b["cod"] or 0),"total_orders":int(c["orders"] or 0),"total_cod":float(c["cod"] or 0),"products":products}


def find_order(value: str) -> sqlite3.Row | None:
    init_db(); value=clean_value(value)
    with connect() as conn:
        return conn.execute("SELECT * FROM orders WHERE consignment=? OR merchant_id=? OR phone=? ORDER BY order_date DESC, imported_at DESC LIMIT 1", (value,value,value)).fetchone()


def all_orders(start_date: str | None = None, end_date: str | None = None, product: str | None = None) -> list[sqlite3.Row]:
    init_db(); conditions=[]; params=[]
    if start_date: conditions.append("order_date>=?"); params.append(start_date)
    if end_date: conditions.append("order_date<=?"); params.append(end_date)
    if product: conditions.append("product=?"); params.append(product)
    where=" WHERE "+" AND ".join(conditions) if conditions else ""
    with connect() as conn:
        return conn.execute(f"SELECT * FROM orders{where} ORDER BY order_date DESC, product, consignment", params).fetchall()


def recent_imports(limit: int = 10) -> list[sqlite3.Row]:
    init_db(); limit=max(1,min(int(limit),100))
    with connect() as conn:
        return conn.execute("SELECT * FROM import_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def get_import(batch_id: str) -> sqlite3.Row | None:
    init_db()
    with connect() as conn:
        return conn.execute("SELECT * FROM import_history WHERE batch_id=?", (batch_id,)).fetchone()



def get_orders_by_batch(batch_id: str) -> list[dict[str, Any]]:
    """Return rows before a synchronized delete."""
    init_db()
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM orders WHERE batch_id=? ORDER BY id",
            (clean_value(batch_id),),
        ).fetchall()]

def delete_import(batch_id: str) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        history = conn.execute("SELECT * FROM import_history WHERE batch_id=?", (batch_id,)).fetchone()
        if not history:
            return {"deleted": False, "orders": 0, "cod": 0.0, "export_files": "", "deleted_rows": []}
        rows = [dict(row) for row in conn.execute("SELECT * FROM orders WHERE batch_id=?", (batch_id,)).fetchall()]
        totals = conn.execute("SELECT COUNT(*) orders, COALESCE(SUM(cod),0) cod FROM orders WHERE batch_id=?", (batch_id,)).fetchone()
        conn.execute("DELETE FROM orders WHERE batch_id=?", (batch_id,))
        conn.execute("DELETE FROM duplicate_history WHERE batch_id=?", (batch_id,))
        conn.execute("DELETE FROM import_history WHERE batch_id=?", (batch_id,))
        return {
            "deleted": True,
            "orders": int(totals["orders"] or 0),
            "cod": float(totals["cod"] or 0),
            "export_files": clean_value(history["export_files"]),
            "deleted_rows": rows,
        }


def delete_order(consignment: str) -> bool:
    init_db()
    with connect() as conn:
        cur=conn.execute("DELETE FROM orders WHERE consignment=?",(clean_value(consignment),))
        return cur.rowcount>0


def duplicate_summary() -> dict[str, Any]:
    init_db(); today=today_iso(); month_start=date.today().replace(day=1).isoformat()
    with connect() as conn:
        total=conn.execute("SELECT COUNT(*) count, COALESCE(SUM(cod),0) cod FROM duplicate_history").fetchone()
        day=conn.execute("SELECT COUNT(*) count FROM duplicate_history WHERE substr(duplicate_at,1,10)=?",(today,)).fetchone()
        month=conn.execute("SELECT COUNT(*) count FROM duplicate_history WHERE substr(duplicate_at,1,10)>=?",(month_start,)).fetchone()
    return {"total":int(total["count"] or 0),"cod":float(total["cod"] or 0),"today":int(day["count"] or 0),"month":int(month["count"] or 0)}


def all_duplicates() -> list[sqlite3.Row]:
    init_db()
    with connect() as conn:
        return conn.execute("SELECT * FROM duplicate_history ORDER BY id DESC").fetchall()


def clear_duplicates() -> int:
    init_db()
    with connect() as conn:
        count=conn.execute("SELECT COUNT(*) c FROM duplicate_history").fetchone()["c"]
        conn.execute("DELETE FROM duplicate_history")
        return int(count or 0)


def today_iso() -> str: return date.today().isoformat()
def yesterday_iso() -> str: return (date.today()-timedelta(days=1)).isoformat()
def month_start_iso() -> str: return date.today().replace(day=1).isoformat()
def last_30_days_iso() -> str: return (date.today()-timedelta(days=29)).isoformat()


def courier_sync_candidates(limit: int = 300) -> list[dict[str, Any]]:
    init_db()
    limit = max(1, min(int(limit), 2000))
    terminal = ("RETURNED", "DELIVERED", "CANCELLED")
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE consignment IS NOT NULL AND trim(consignment) != ''
              AND COALESCE(courier_status, 'UNKNOWN') NOT IN (?, ?, ?)
            ORDER BY COALESCE(courier_synced_at, '') ASC, id DESC
            LIMIT ?
            """,
            (*terminal, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def update_courier_status(consignment: str, status: str, courier_cod: float | None = None, raw_json: str = "") -> dict[str, Any] | None:
    init_db()
    now = datetime.now().isoformat(timespec="seconds")
    normalized = clean_value(status).upper() or "UNKNOWN"
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE lower(consignment)=lower(?) LIMIT 1",
            (clean_value(consignment),),
        ).fetchone()
        if not row:
            return None
        old_status = clean_value(row["courier_status"]).upper() or "UNKNOWN"
        effective_cod = float(courier_cod) if courier_cod is not None else float(row["cod"] or 0)
        returned_at = row["returned_at"]
        delivered_at = row["delivered_at"]
        if normalized == "RETURNED" and old_status != "RETURNED":
            returned_at = now
        if normalized == "DELIVERED" and old_status != "DELIVERED":
            delivered_at = now
        conn.execute(
            """
            UPDATE orders
            SET courier_status=?, courier_cod=?, courier_synced_at=?, returned_at=?, delivered_at=?, courier_raw=?
            WHERE id=?
            """,
            (normalized, effective_cod, now, returned_at, delivered_at, clean_value(raw_json), row["id"]),
        )
        updated = dict(row)
        updated.update({
            "old_status": old_status,
            "courier_status": normalized,
            "courier_cod": effective_cod,
            "courier_synced_at": now,
            "returned_at": returned_at,
            "delivered_at": delivered_at,
            "status_changed": old_status != normalized,
        })
        return updated


def courier_summary(start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    init_db()
    conditions = []
    params: list[Any] = []
    if start_date:
        conditions.append("order_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("order_date <= ?")
        params.append(end_date)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT
                COUNT(*) total_parcels,
                COALESCE(SUM(cod),0) total_cod,
                SUM(CASE WHEN courier_status='RETURNED' THEN 1 ELSE 0 END) return_parcels,
                COALESCE(SUM(CASE WHEN courier_status='RETURNED' THEN COALESCE(courier_cod,cod) ELSE 0 END),0) return_cod,
                SUM(CASE WHEN courier_status='DELIVERED' THEN 1 ELSE 0 END) delivered_parcels,
                COALESCE(SUM(CASE WHEN courier_status='DELIVERED' THEN COALESCE(courier_cod,cod) ELSE 0 END),0) delivered_cod,
                SUM(CASE WHEN courier_status IN ('PENDING','IN_TRANSIT','UNKNOWN') THEN 1 ELSE 0 END) active_parcels
            FROM orders{where}
            """,
            params,
        ).fetchone()
        products = conn.execute(
            f"""
            SELECT product,
                   SUM(CASE WHEN courier_status='RETURNED' THEN 1 ELSE 0 END) return_parcels,
                   COALESCE(SUM(CASE WHEN courier_status='RETURNED' THEN COALESCE(courier_cod,cod) ELSE 0 END),0) return_cod
            FROM orders{where}
            GROUP BY product
            HAVING return_parcels > 0
            ORDER BY return_parcels DESC, product
            """,
            params,
        ).fetchall()
    total_cod = float(row["total_cod"] or 0)
    return_cod = float(row["return_cod"] or 0)
    return {
        "total_parcels": int(row["total_parcels"] or 0),
        "total_cod": total_cod,
        "return_parcels": int(row["return_parcels"] or 0),
        "return_cod": return_cod,
        "net_parcels": int(row["total_parcels"] or 0) - int(row["return_parcels"] or 0),
        "net_cod": total_cod - return_cod,
        "delivered_parcels": int(row["delivered_parcels"] or 0),
        "delivered_cod": float(row["delivered_cod"] or 0),
        "active_parcels": int(row["active_parcels"] or 0),
        "products": products,
    }
