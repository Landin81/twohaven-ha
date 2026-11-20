"""Konfigurera TwoHaven: klistra in API-nyckeln från appen (Mer → Home Assistant)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TwoHavenApi, TwoHavenAuthError, TwoHavenError
from .const import CONF_URL, DEFAULT_URL, DOMAIN


class TwoHavenConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _check(self, key: str, url: str) -> tuple[dict[str, Any] | None, dict[str, str]]:
        try:
            return await TwoHavenApi(async_get_clientsession(self.hass), key, url).status(), {}
        except TwoHavenAuthError:
            return None, {"base": "invalid_auth"}
        except TwoHavenError:
            return None, {"base": "cannot_connect"}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip().removeprefix("Bearer ").strip()
            url = (user_input.get(CONF_URL) or DEFAULT_URL).strip()
            status, errors = await self._check(key, url)
            if status is not None:
                await self.async_set_unique_id(f"{url}#{status.get('familyId')}")
                self._abort_if_unique_id_configured(updates={CONF_API_KEY: key})
                return self.async_create_entry(title=f"TwoHaven – {status.get('family') or 'familjen'}", data={CONF_API_KEY: key, CONF_URL: url})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str, vol.Optional(CONF_URL, default=DEFAULT_URL): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip().removeprefix("Bearer ").strip()
            status, errors = await self._check(key, entry.data.get(CONF_URL, DEFAULT_URL))
            if status is not None:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_API_KEY: key})
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}), errors=errors)
