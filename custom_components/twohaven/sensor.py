"""Sensorer per barn: skärmtid kvar, använd, bonus och sysslor som väntar."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import TwoHavenChildEntity


@dataclass(frozen=True, kw_only=True)
class ChildSensor(SensorEntityDescription):
    value: Callable[[dict[str, Any]], Any]
    attrs: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSORS = (
    ChildSensor(key="remaining_today", icon="mdi:timer-sand", native_unit_of_measurement=UnitOfTime.MINUTES,
                device_class=SensorDeviceClass.DURATION, value=lambda c: c.get("remainingToday")),
    ChildSensor(key="used_today", icon="mdi:cellphone-clock", native_unit_of_measurement=UnitOfTime.MINUTES,
                device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.TOTAL_INCREASING, value=lambda c: c.get("usedToday")),
    ChildSensor(key="bonus_today", icon="mdi:gift-outline", native_unit_of_measurement=UnitOfTime.MINUTES, value=lambda c: c.get("bonusToday")),
    ChildSensor(key="pending_chores", icon="mdi:broom", value=lambda c: len(c.get("pendingChores") or []),
                attrs=lambda c: {"chores": c.get("pendingChores") or []}),
    ChildSensor(key="current_app", icon="mdi:application",
                value=lambda c: next((d.get("currentApp") for d in c.get("devices", []) if d.get("online") and d.get("currentApp")), None),
                attrs=lambda c: {"devices": [{k: d.get(k) for k in ("name", "online", "locked", "battery", "currentApp", "usedToday", "remainingToday")} for d in c.get("devices", [])]}),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    add(TwoHavenSensor(coord, c["id"], d) for c in coord.data.get("children", []) for d in SENSORS)


class TwoHavenSensor(TwoHavenChildEntity, SensorEntity):
    entity_description: ChildSensor

    def __init__(self, coordinator, child_id: int, description: ChildSensor) -> None:
        super().__init__(coordinator, child_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        c = self.child
        if not c:
            return None
        v = self.entity_description.value(c)
        if isinstance(v, dict):
            return v.get("label") or v.get("package")
        return v

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        c = self.child
        return self.entity_description.attrs(c) if c and self.entity_description.attrs else None
