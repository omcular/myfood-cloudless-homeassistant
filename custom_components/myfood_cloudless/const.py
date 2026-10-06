"""Constants for the myfood cloudless integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature

DOMAIN = "myfood_cloudless"

CONF_HOST = "host"
CONF_VHOST = "vhost"
CONF_PORT = "port"

DEFAULT_HOST = "myfoodpi"
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

# (data key, entity name, unit, device_class, state_class)
SENSORS: tuple[tuple, ...] = (
    ("ph", "pH", None, SensorDeviceClass.PH, SensorStateClass.MEASUREMENT),
    ("water_temp", "Water temperature", UnitOfTemperature.CELSIUS,
     SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ("air_temp", "Air temperature", UnitOfTemperature.CELSIUS,
     SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ("humidity", "Humidity", PERCENTAGE,
     SensorDeviceClass.HUMIDITY, SensorStateClass.MEASUREMENT),
)
