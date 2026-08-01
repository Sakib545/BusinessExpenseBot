from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import aiohttp


class PathaoError(RuntimeError):
    pass


@dataclass
class PathaoOrderStatus:
    consignment_id: str
    merchant_order_id: str
    status: str
    cod: float | None
    raw: dict[str, Any]


class PathaoClient:
    """Minimal Pathao Courier API client.

    Endpoints are environment-configurable because Pathao accounts/API versions can differ.
    The defaults match the commonly used Courier merchant API.
    """

    def __init__(self) -> None:
        self.base_url = os.getenv("PATHAO_BASE_URL", "https://api-hermes.pathao.com/aladdin/api/v1").rstrip("/")
        self.client_id = os.getenv("PATHAO_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("PATHAO_CLIENT_SECRET", "").strip()
        self.username = os.getenv("PATHAO_USERNAME", os.getenv("PATHAO_MERCHANT_EMAIL", "")).strip()
        self.password = os.getenv("PATHAO_PASSWORD", os.getenv("PATHAO_MERCHANT_PASSWORD", "")).strip()
        self.access_token = os.getenv("PATHAO_ACCESS_TOKEN", "").strip()
        self.token_endpoint = os.getenv("PATHAO_TOKEN_ENDPOINT", "/issue-token").strip()
        self.order_info_endpoint = os.getenv("PATHAO_ORDER_INFO_ENDPOINT", "/orders/{consignment_id}/info").strip()
        self.timeout = int(os.getenv("PATHAO_HTTP_TIMEOUT", "25"))
        self._token = self.access_token
        self._token_expires_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.access_token or (self.client_id and self.client_secret and self.username and self.password))

    def _url(self, endpoint: str) -> str:
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    async def _get_token(self, session: aiohttp.ClientSession) -> str:
        if self._token and (self.access_token or time.time() < self._token_expires_at - 60):
            return self._token
        if not self.configured:
            raise PathaoError("Pathao credentials configure করা হয়নি।")
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
        }
        async with session.post(self._url(self.token_endpoint), json=payload) as response:
            data = await self._json(response)
            token = str(data.get("access_token") or data.get("token") or "").strip()
            if not token:
                raise PathaoError(f"Pathao access token পাওয়া যায়নি: {data}")
            self._token = token
            self._token_expires_at = time.time() + int(data.get("expires_in") or 3600)
            return token

    async def get_order_status(self, consignment_id: str) -> PathaoOrderStatus:
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            token = await self._get_token(session)
            endpoint = self.order_info_endpoint.format(consignment_id=consignment_id)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            async with session.get(self._url(endpoint), headers=headers) as response:
                payload = await self._json(response)

        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        status = self._first(data, "order_status", "status", "delivery_status", "current_status")
        merchant_order_id = self._first(data, "merchant_order_id", "merchant_id", "order_id")
        returned_consignment = self._first(data, "consignment_id", "consignment", "tracking_id") or consignment_id
        cod_raw = self._first(data, "amount_to_collect", "cod", "cod_amount", "collection_amount")
        try:
            cod = float(cod_raw) if cod_raw not in (None, "") else None
        except (TypeError, ValueError):
            cod = None
        return PathaoOrderStatus(
            consignment_id=str(returned_consignment),
            merchant_order_id=str(merchant_order_id or ""),
            status=str(status or "UNKNOWN"),
            cod=cod,
            raw=payload,
        )

    @staticmethod
    async def _json(response: aiohttp.ClientResponse) -> dict[str, Any]:
        try:
            data = await response.json(content_type=None)
        except Exception:
            text = await response.text()
            raise PathaoError(f"Pathao invalid response ({response.status}): {text[:300]}")
        if response.status >= 400:
            raise PathaoError(f"Pathao API error ({response.status}): {data}")
        if not isinstance(data, dict):
            raise PathaoError(f"Pathao unexpected response: {data}")
        return data

    @staticmethod
    def _first(data: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        return None


def normalize_status(value: str) -> str:
    text = " ".join(str(value or "").replace("_", " ").replace("-", " ").upper().split())
    if any(word in text for word in ("RETURNED", "RETURN", "FAILED DELIVERY", "DELIVERY FAILED")):
        return "RETURNED"
    if any(word in text for word in ("DELIVERED", "DELIVERY SUCCESS", "SUCCESSFUL DELIVERY")):
        return "DELIVERED"
    if "CANCEL" in text:
        return "CANCELLED"
    if any(word in text for word in ("PICKED", "PICKUP", "IN TRANSIT", "OUT FOR DELIVERY", "ASSIGNED")):
        return "IN_TRANSIT"
    if any(word in text for word in ("PENDING", "CREATED", "REQUESTED")):
        return "PENDING"
    return text or "UNKNOWN"
