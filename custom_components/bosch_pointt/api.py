"""Thin async client for the Bosch Pointt REST API."""
from __future__ import annotations

import logging
import time

import aiohttp

from .const import API_BASE, CLIENT_ID, TOKEN_URL

_LOGGER = logging.getLogger(__name__)


class PointtAuthError(Exception):
    """Raised when the refresh token is no longer valid (needs re-login)."""


class PointtApi:
    """Handles token refresh + REST calls to the Pointt API."""

    def __init__(self, session: aiohttp.ClientSession, refresh_token: str) -> None:
        self._session = session
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._access_token_expires: float = 0.0

    @property
    def refresh_token(self) -> str:
        """Current refresh token (may rotate after each use)."""
        return self._refresh_token

    async def _ensure_access_token(self) -> str:
        if self._access_token and time.monotonic() < self._access_token_expires:
            return self._access_token

        async with self._session.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": CLIENT_ID,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        ) as resp:
            if resp.status == 400:
                raise PointtAuthError(
                    "Refresh token rejected -- log in again in the app and update the hardcoded token."
                )
            resp.raise_for_status()
            tokens = await resp.json()

        self._access_token = tokens["access_token"]
        # Refresh a bit early to avoid racing expiry.
        self._access_token_expires = time.monotonic() + tokens["expires_in"] - 60
        if tokens.get("refresh_token"):
            self._refresh_token = tokens["refresh_token"]
        return self._access_token

    async def _request(self, method: str, url: str, **kwargs):
        token = await self._ensure_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        async with self._session.request(method, url, headers=headers, **kwargs) as resp:
            resp.raise_for_status()
            if resp.status == 204 or resp.content_length == 0:
                return None
            return await resp.json()

    async def get_gateways(self):
        return await self._request("GET", f"{API_BASE}/gateways")

    async def get_resource(self, device_id: str, path: str):
        return await self._request("GET", f"{API_BASE}/gateways/{device_id}/resource/{path}")

    async def put_resource(self, device_id: str, path: str, value) -> None:
        await self._request(
            "PUT",
            f"{API_BASE}/gateways/{device_id}/resource/{path}",
            json={"value": value},
        )
