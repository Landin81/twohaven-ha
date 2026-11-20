"""Enkel klient för TwoHavens API för smarta hem."""
from __future__ import annotations

from typing import Any

import aiohttp


class TwoHavenError(Exception):
    """Allmänt fel från TwoHaven."""


class TwoHavenAuthError(TwoHavenError):
    """API-nyckeln är fel eller borttagen."""


class TwoHavenApi:
    """Pratar med api.twohaven.se med en API-nyckel (Bearer th_…)."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str, url: str) -> None:
        self._session = session
        self._key = api_key.strip()
        self._base = url.rstrip("/") + "/api/ha/v1"

    async def _req(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with self._session.request(
                method,
                self._base + path,
                json=body if body is not None else ({} if method == "POST" else None),
                headers={"Authorization": f"Bearer {self._key}"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 401:
                    raise TwoHavenAuthError(data.get("error", "Ogiltig API-nyckel"))
                if resp.status >= 400:
                    raise TwoHavenError(data.get("error", f"HTTP {resp.status}"))
                return data
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TwoHavenError(f"Kunde inte nå TwoHaven: {err}") from err

    async def status(self) -> dict[str, Any]:
        return await self._req("GET", "/status")

    async def bonus(self, child: str, minutes: int, reason: str | None = None, once: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {"minutes": minutes, "once": once}
        if reason:
            body["reason"] = reason
        return await self._req("POST", f"/children/{child}/bonus", body)

    async def lock(self, child: str, minutes: int = 0, device: str | None = None) -> dict[str, Any]:
        return await self._req("POST", f"/children/{child}/lock", {"minutes": minutes, **({"device": device} if device else {})})

    async def unlock(self, child: str, device: str | None = None) -> dict[str, Any]:
        return await self._req("POST", f"/children/{child}/unlock", {"device": device} if device else {})

    async def open(self, child: str, minutes: int, device: str | None = None) -> dict[str, Any]:
        return await self._req("POST", f"/children/{child}/open", {"minutes": minutes, **({"device": device} if device else {})})

    async def internet(self, child: str, off: bool, device: str | None = None) -> dict[str, Any]:
        return await self._req("POST", f"/children/{child}/internet", {"off": off, **({"device": device} if device else {})})

    async def ring(self, child: str, device: str | None = None) -> dict[str, Any]:
        return await self._req("POST", f"/children/{child}/ring", {"device": device} if device else {})

    async def chore(self, child: str, name: str, minutes: int, penalty_factor: float = 2) -> dict[str, Any]:
        return await self._req("POST", f"/children/{child}/chores", {"name": name, "minutes": minutes, "penaltyFactor": penalty_factor})

    async def decide_chore(self, chore_id: int, ok: bool) -> dict[str, Any]:
        return await self._req("POST", f"/chores/{chore_id}/{'approve' if ok else 'reject'}")
