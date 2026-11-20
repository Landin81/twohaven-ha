"""Binära sensorer per barn: låst och online."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import TwoHavenChildEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    ents = []
    for c in coord.data.get("children", []):
        ents += [Locked(coord, c["id"], "locked"), Online(coord, c["id"], "online")]
    add(ents)


class Locked(TwoHavenChildEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool | None:
        return bool(self.child.get("locked")) if self.child else None

    @property
    def icon(self) -> str:
        return "mdi:lock" if self.is_on else "mdi:lock-open-variant"


class Online(TwoHavenChildEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool | None:
        return bool(self.child.get("anyOnline")) if self.child else None
