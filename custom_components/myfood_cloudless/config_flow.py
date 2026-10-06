"""Config flow for myfood cloudless."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_HOST, CONF_PORT, CONF_VHOST, DEFAULT_HOST, DEFAULT_PORT, DOMAIN
from .reader import Reader


class MyfoodConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for myfood cloudless."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            reader = Reader(
                host=user_input[CONF_HOST],
                vhost=user_input.get(CONF_VHOST) or None,
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
            )
            try:
                await self.hass.async_add_executor_job(reader.read)
            except Exception:  # noqa: BLE001 - any failure means we can't connect
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input.get(CONF_PORT, DEFAULT_PORT)}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Optional(CONF_VHOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
