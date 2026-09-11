"""Sensor entities for the Bosch EasyControl gateway."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BoschPointtCoordinator
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BoschPointtSensor(coordinator, "outdoor_temp", "Outdoor Temperature", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
            BoschPointtSensor(coordinator, "indoor_humidity", "Indoor Humidity", SensorDeviceClass.HUMIDITY, PERCENTAGE),
            BoschPointtSensor(coordinator, "firmware_version", "Firmware Version", None, None),
            BoschPointtSensor(coordinator, "hot_water_system", "Hot Water System", None, None),
            BoschPointtSensor(coordinator, "system_pressure", "System Pressure", SensorDeviceClass.PRESSURE, UnitOfPressure.BAR),
            BoschPointtModulationSensor(coordinator),
            BoschPointtNotificationsSensor(coordinator),
        ]
    )


class BoschPointtSensor(CoordinatorEntity[BoschPointtCoordinator], SensorEntity):
    def __init__(self, coordinator, key: str, name: str, device_class, unit) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class BoschPointtModulationSensor(CoordinatorEntity[BoschPointtCoordinator], SensorEntity):
    """heatSources/modulation returns a stringArray, e.g. ["70", "0"] -- first
    element is current burner modulation %. Second element's meaning is
    unconfirmed (always seen as "0" so far)."""

    _attr_name = "Burner Modulation"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_heat_source_modulation"

    @property
    def native_value(self):
        value = self.coordinator.data.get("heat_source_modulation")
        if not value:
            return None
        try:
            return float(value[0])
        except (TypeError, ValueError, IndexError):
            return None


class BoschPointtNotificationsSensor(CoordinatorEntity[BoschPointtCoordinator], SensorEntity):
    """Active fault/error list -- the equivalent of the reference
    integration's boiler cause codes. Raw entries exposed as an attribute
    since we've never seen a populated one (no fault occurred during
    capture) and so don't know the field names inside each entry yet."""

    _attr_name = "Active Notifications"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_notifications"

    @property
    def native_value(self):
        notifications = self.coordinator.data.get("notifications") or []
        return len(notifications)

    @property
    def extra_state_attributes(self):
        return {"notifications": self.coordinator.data.get("notifications") or []}
