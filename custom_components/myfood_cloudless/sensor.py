"""Sensor entities for myfood cloudless."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSORS
from .coordinator import MyfoodCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the four greenhouse sensors from a config entry."""
    coordinator: MyfoodCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(MyfoodSensor(coordinator, entry, *spec) for spec in SENSORS)


class MyfoodSensor(CoordinatorEntity[MyfoodCoordinator], SensorEntity):
    """A single greenhouse measurement."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, name, unit, device_class, state_class) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="myfood Greenhouse",
            manufacturer="myfood",
            model="App Core (local)",
        )

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self._key)

    @property
    def extra_state_attributes(self):
        return {"last_sample": (self.coordinator.data or {}).get("last_sample")}
