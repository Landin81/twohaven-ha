"""Gemensam bas: varje barn blir en enhet i Home Assistant."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TwoHavenCoordinator


class TwoHavenChildEntity(CoordinatorEntity[TwoHavenCoordinator]):
    """En entitet som hör till ett barn."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TwoHavenCoordinator, child_id: int, key: str) -> None:
        super().__init__(coordinator)
        self.child_id = child_id
        fam = coordinator.data.get("familyId", coordinator.entry.entry_id)
        self._attr_unique_id = f"{fam}_{child_id}_{key}"
        self._attr_translation_key = key
        c = self.child or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{fam}_{child_id}")},
            name=c.get("name", f"Barn {child_id}"),
            manufacturer="TwoHaven",
            model=coordinator.data.get("family") or "TwoHaven",
        )

    @property
    def child(self) -> dict[str, Any] | None:
        return self.coordinator.child(self.child_id)

    @property
    def child_key(self) -> str:
        return str(self.child_id)

    @property
    def available(self) -> bool:
        return super().available and self.child is not None
