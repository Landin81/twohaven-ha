"""Hämtar status från TwoHaven en gång i minuten."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TwoHavenApi, TwoHavenAuthError, TwoHavenError
from .const import DOMAIN, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class TwoHavenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data: {"family": …, "children": [...], "byId": {id: child}}."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: TwoHavenApi) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS))
        self.entry = entry
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.status()
        except TwoHavenAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TwoHavenError as err:
            raise UpdateFailed(str(err)) from err
        data["byId"] = {c["id"]: c for c in data.get("children", [])}
        return data

    def child(self, child_id: int) -> dict[str, Any] | None:
        return (self.data or {}).get("byId", {}).get(child_id)

    def apply_child(self, child: dict[str, Any] | None) -> None:
        """Uppdatera ett barn direkt från ett svar (så att knappar och brytare känns snabba)."""
        if not child or not self.data:
            return
        self.data["byId"][child["id"]] = {**self.data["byId"].get(child["id"], {}), **child}
        self.data["children"] = [self.data["byId"].get(c["id"], c) for c in self.data.get("children", [])]
        self.async_set_updated_data(self.data)
