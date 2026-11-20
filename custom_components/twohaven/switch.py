"""Brytare per barn: lås alla enheter och internet."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import TwoHavenError
from .const import DOMAIN
from .entity import TwoHavenChildEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    ents = []
    for c in coord.data.get("children", []):
        ents += [LockSwitch(coord, c["id"], "lock"), InternetSwitch(coord, c["id"], "internet")]
    add(ents)


class _Base(TwoHavenChildEntity, SwitchEntity):
    async def _do(self, coro) -> None:
        try:
            res = await coro
        except TwoHavenError as err:
            raise HomeAssistantError(str(err)) from err
        self.coordinator.apply_child(res.get("child"))


class LockSwitch(_Base):
    """På = alla barnets enheter är låsta."""

    @property
    def is_on(self) -> bool | None:
        return bool(self.child.get("locked")) if self.child else None

    @property
    def icon(self) -> str:
        return "mdi:lock" if self.is_on else "mdi:lock-open-variant"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._do(self.coordinator.api.lock(self.child_key))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._do(self.coordinator.api.unlock(self.child_key))


class InternetSwitch(_Base):
    """På = internet fungerar (inte avstängt av förälder)."""

    @property
    def is_on(self) -> bool | None:
        if not self.child:
            return None
        return not any(d.get("internetOff") for d in self.child.get("devices", []))

    @property
    def icon(self) -> str:
        return "mdi:web" if self.is_on else "mdi:web-off"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._do(self.coordinator.api.internet(self.child_key, False))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._do(self.coordinator.api.internet(self.child_key, True))
