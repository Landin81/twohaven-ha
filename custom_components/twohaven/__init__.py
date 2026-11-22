"""TwoHaven – skärmtid för barnen i Home Assistant."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TwoHavenApi, TwoHavenError
from .const import (
    ATTR_CHILD, ATTR_CHORE_ID, ATTR_DEVICE, ATTR_ENTRY, ATTR_MINUTES, ATTR_NAME, ATTR_OFF, ATTR_ONCE,
    ATTR_PENALTY_FACTOR, ATTR_REASON, CONF_URL, DEFAULT_URL, DOMAIN, EVENT_CHORE_CLAIMED, EVENT_CHORE_DECIDED,
)
from .coordinator import TwoHavenCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON]

BASE = {vol.Optional(ATTR_ENTRY): cv.string}
CHILD = {**BASE, vol.Required(ATTR_CHILD): cv.string}
SCHEMAS = {
    "give_bonus": vol.Schema({**CHILD, vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=-120, max=120)),
                              vol.Optional(ATTR_REASON): cv.string, vol.Optional(ATTR_ONCE, default=False): cv.boolean}),
    "chore": vol.Schema({**CHILD, vol.Required(ATTR_NAME): cv.string, vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
                         vol.Optional(ATTR_PENALTY_FACTOR, default=2): vol.All(vol.Coerce(float), vol.Range(min=0, max=5))}),
    "approve_chore": vol.Schema({**BASE, vol.Required(ATTR_CHORE_ID): vol.Coerce(int)}),
    "reject_chore": vol.Schema({**BASE, vol.Required(ATTR_CHORE_ID): vol.Coerce(int)}),
    "lock": vol.Schema({**CHILD, vol.Optional(ATTR_MINUTES, default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=1440)), vol.Optional(ATTR_DEVICE): cv.string}),
    "unlock": vol.Schema({**CHILD, vol.Optional(ATTR_DEVICE): cv.string}),
    "open": vol.Schema({**CHILD, vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=0, max=240)), vol.Optional(ATTR_DEVICE): cv.string}),
    "internet": vol.Schema({**CHILD, vol.Required(ATTR_OFF): cv.boolean, vol.Optional(ATTR_DEVICE): cv.string}),
    "ring": vol.Schema({**CHILD, vol.Optional(ATTR_DEVICE): cv.string}),
    # Spelkonsol (t.ex. Nintendo Switch): rapportera dagens speltid, få tillbaka hur länge den får användas idag
    "console": vol.Schema({**CHILD, vol.Optional(ATTR_NAME, default="Nintendo Switch"): cv.string,
                           vol.Required("used_today"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1440))}),
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = TwoHavenApi(async_get_clientsession(hass), entry.data[CONF_API_KEY], entry.data.get(CONF_URL, DEFAULT_URL))
    coordinator = TwoHavenCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            for name in SCHEMAS:
                hass.services.async_remove(DOMAIN, name)
    return ok


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> TwoHavenCoordinator:
    coords: dict[str, TwoHavenCoordinator] = hass.data.get(DOMAIN, {})
    if not coords:
        raise ServiceValidationError("TwoHaven är inte konfigurerat")
    entry_id = call.data.get(ATTR_ENTRY)
    if entry_id:
        if entry_id not in coords:
            raise ServiceValidationError(f"Okänd TwoHaven-post: {entry_id}")
        return coords[entry_id]
    return next(iter(coords.values()))


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "give_bonus"):
        return

    async def run(call: ServiceCall) -> ServiceResponse:
        coord = _coordinator(hass, call)
        api, d = coord.api, call.data
        child, dev = d.get(ATTR_CHILD), d.get(ATTR_DEVICE)
        try:
            name = call.service
            if name == "give_bonus":
                res = await api.bonus(child, d[ATTR_MINUTES], d.get(ATTR_REASON), d[ATTR_ONCE])
            elif name == "chore":
                res = await api.chore(child, d[ATTR_NAME], d[ATTR_MINUTES], d[ATTR_PENALTY_FACTOR])
                ch = res.get("chore") or {}
                hass.bus.async_fire(EVENT_CHORE_CLAIMED, {**ch, "already_claimed": bool(res.get("alreadyClaimed")), "entry_id": coord.entry.entry_id})
            elif name in ("approve_chore", "reject_chore"):
                res = await api.decide_chore(d[ATTR_CHORE_ID], name == "approve_chore")
                hass.bus.async_fire(EVENT_CHORE_DECIDED, {**(res.get("chore") or {}), "entry_id": coord.entry.entry_id})
            elif name == "lock":
                res = await api.lock(child, d[ATTR_MINUTES], dev)
            elif name == "unlock":
                res = await api.unlock(child, dev)
            elif name == "open":
                res = await api.open(child, d[ATTR_MINUTES], dev)
            elif name == "internet":
                res = await api.internet(child, d[ATTR_OFF], dev)
            elif name == "console":
                res = await api.console(child, d[ATTR_NAME], int(d["used_today"]))
            else:
                res = await api.ring(child, dev)
        except TwoHavenError as err:
            raise HomeAssistantError(str(err)) from err
        if res.get("child"):
            coord.apply_child(res.get("child"))
        else:
            await coord.async_refresh()
        if call.return_response:
            out: dict[str, Any] = {k: v for k, v in res.items() if k != "child"}
            return out
        return None

    for name, schema in SCHEMAS.items():
        hass.services.async_register(DOMAIN, name, run, schema=schema, supports_response=SupportsResponse.OPTIONAL)
