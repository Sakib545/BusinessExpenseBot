from __future__ import annotations
import json, os, tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
if not DATA_DIR.exists():
    DATA_DIR = Path(tempfile.gettempdir()) / "buraq_data"
PENDING_DIR = DATA_DIR / "central_pending"
STATUS_FILE = DATA_DIR / "central_offline_status.json"

def _atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    temp.replace(path)

def _safe(source: str) -> str:
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in source)

def path_for(source: str) -> Path:
    return PENDING_DIR / f"{_safe(source)}.json"

def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None

def count_pending() -> int:
    try:
        return len(list(PENDING_DIR.glob("*.json")))
    except OSError:
        return 0

def queue_snapshot(source: str, title: str, headers: list[str], rows: list[list[Any]]) -> Path:
    path = path_for(source)
    old = _load(path) or {}
    _atomic(path, {
        "source": source,
        "title": title,
        "headers": headers,
        "rows": rows,
        "created_at": old.get("created_at") or datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "retry_count": int(old.get("retry_count") or 0),
        "last_error": old.get("last_error") or "",
    })
    return path

def _failed(path: Path, exc: Exception) -> None:
    payload = _load(path) or {}
    payload["retry_count"] = int(payload.get("retry_count") or 0) + 1
    payload["last_attempt"] = datetime.now().isoformat(timespec="seconds")
    payload["last_error"] = f"{type(exc).__name__}: {exc}"[:1000]
    _atomic(path, payload)
    _atomic(STATUS_FILE, {
        "state": "OFFLINE",
        "last_attempt": payload["last_attempt"],
        "last_error": payload["last_error"],
        "pending_files": count_pending(),
    })

def _success(path: Path, source: str, rows: int) -> None:
    path.unlink(missing_ok=True)
    _atomic(STATUS_FILE, {
        "state": "ONLINE",
        "last_success": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "rows": rows,
        "pending_files": count_pending(),
    })

def sync_snapshot(source: str, title: str, headers: list[str], rows: list[list[Any]],
                  uploader: Callable[[str, list[str], list[list[Any]]], int]) -> dict[str, Any]:
    path = queue_snapshot(source, title, headers, rows)
    try:
        synced = uploader(title, headers, rows)
        _success(path, source, synced)
        return {"synced": synced, "queued": False, "pending": count_pending(), "error": ""}
    except Exception as exc:
        _failed(path, exc)
        return {"synced": 0, "queued": True, "pending": count_pending(),
                "error": f"{type(exc).__name__}: {exc}"}

def flush_snapshot(source: str, uploader: Callable[[str, list[str], list[list[Any]]], int]) -> dict[str, Any]:
    path = path_for(source)
    payload = _load(path)
    if not payload:
        return {"synced": 0, "queued": False, "pending": count_pending(), "error": ""}
    try:
        synced = uploader(payload["title"], payload["headers"], payload["rows"])
        _success(path, source, synced)
        return {"synced": synced, "queued": False, "pending": count_pending(), "error": ""}
    except Exception as exc:
        _failed(path, exc)
        return {"synced": 0, "queued": True, "pending": count_pending(),
                "error": f"{type(exc).__name__}: {exc}"}
