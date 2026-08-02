
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def upload_central_export(
    file_path: Path,
    *,
    kind: str,
    month: str,
    timeout: int = 45,
) -> dict[str, Any]:
    """
    Upload a generated Central Export workbook to BURAQ Central Bot.

    Required environment variables:
      CENTRAL_API_URL=https://your-central-service.up.railway.app/api/upload
      CENTRAL_API_SECRET=long-random-secret
    """
    url = os.getenv("CENTRAL_API_URL", "").strip()
    secret = os.getenv("CENTRAL_API_SECRET", "").strip()

    if not url or not secret:
        return {
            "ok": False,
            "configured": False,
            "message": "CENTRAL_API_URL / CENTRAL_API_SECRET সেট করা নেই",
        }

    path = Path(file_path)
    if not path.is_file():
        return {
            "ok": False,
            "configured": True,
            "message": f"Export file পাওয়া যায়নি: {path}",
        }

    payload = {
        "kind": kind,
        "month": month,
        "filename": path.name,
        "content_b64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }

    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Central-Secret": secret,
            "User-Agent": "BURAQ-Central-Sync/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            result = json.loads(body) if body else {}
            result.setdefault("ok", 200 <= response.status < 300)
            result["configured"] = True
            return result
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("message", body)
        except json.JSONDecodeError:
            detail = body
        return {
            "ok": False,
            "configured": True,
            "message": f"Central API {exc.code}: {detail}",
        }
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "configured": True,
            "message": f"Central sync failed: {exc}",
        }
