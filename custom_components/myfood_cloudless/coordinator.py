"""Data update coordinator for myfood cloudless."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_HOST, CONF_PORT, CONF_VHOST, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN
from .reader import Reader

_LOGGER = logging.getLogger(__name__)


class MyfoodCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the greenhouse controller and share the latest reading."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL)
        self.entry = entry
        self._reader = Reader(
            host=entry.data[CONF_HOST],
            vhost=entry.data.get(CONF_VHOST) or None,
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.hass.async_add_executor_job(self._reader.read)
        except Exception as err:  # noqa: BLE001 - surface any reader failure uniformly
            raise UpdateFailed(str(err)) from err
