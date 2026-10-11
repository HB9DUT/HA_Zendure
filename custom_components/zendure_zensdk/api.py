"""Local HTTP client for the Zendure zenSDK."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp

REQUEST_TIMEOUT = 10


class ZendureApiError(Exception):
    """Raised when the device cannot be reached or answers invalidly."""


class ZendureApi:
    """Thin wrapper around /properties/report and /properties/write."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self.host = host

    @property
    def _base(self) -> str:
        return f"http://{self.host}"

    async def async_get_report(self) -> dict[str, Any]:
        """Return the full device report."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(f"{self._base}/properties/report")
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise ZendureApiError(str(err)) from err
        if not isinstance(data, dict) or "properties" not in data:
            raise ZendureApiError("Unexpected report format")
        return data

    async def async_write(self, serial: str, properties: dict[str, Any]) -> None:
        """Write properties to the device."""
        payload = json.dumps({"sn": serial, "properties": properties})
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.post(
                    f"{self._base}/properties/write",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Encoding": "identity",
                    },
                )
                resp.raise_for_status()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ZendureApiError(str(err)) from err
