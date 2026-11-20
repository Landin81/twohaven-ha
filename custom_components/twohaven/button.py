"""Knappar per barn: +15 min bonus och spela ljud."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
        ents += [BonusButton(coord, c["id"], "bonus_15"), RingButton(coord, c["id"], "ring")]
    add(ents)


class BonusButton(TwoHavenChildEntity, ButtonEntity):
    _attr_icon = "mdi:timer-plus-outline"

    async def async_press(self) -> None:
        try:
            res = await self.coordinator.api.bonus(self.child_key, 15, "Home Assistant")
        except TwoHavenError as err:
            raise HomeAssistantError(str(err)) from err
        self.coordinator.apply_child(res.get("child"))


class RingButton(TwoHavenChildEntity, ButtonEntity):
    _attr_icon = "mdi:bell-ring-outline"

    async def async_press(self) -> None:
        try:
            await self.coordinator.api.ring(self.child_key)
        except TwoHavenError as err:
            raise HomeAssistantError(str(err)) from err
