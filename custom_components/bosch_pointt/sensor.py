"""Sensor entities for the Bosch EasyControl gateway."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BoschPointtEntity, burner_modulation
from .const import DOMAIN, ZONE_NUMBER


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BoschPointtSensor(coordinator, "outdoor_temp", "Outdoor Temperature", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
            BoschPointtSensor(coordinator, "indoor_humidity", "Indoor Humidity", SensorDeviceClass.HUMIDITY, PERCENTAGE),
            BoschPointtSensor(coordinator, "firmware_version", "Firmware Version", None, None),
            BoschPointtSensor(coordinator, "hot_water_system", "Hot Water System", None, None),
            BoschPointtSensor(coordinator, "system_pressure", "System Pressure", SensorDeviceClass.PRESSURE, UnitOfPressure.BAR),
            BoschPointtSensor(
                coordinator, "heating_control", "Heating Control", None, None,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            BoschPointtModulationSensor(coordinator),
            BoschPointtNotificationsSensor(coordinator),
            BoschPointtZoneStatusSensor(coordinator),
        ]
    )


class BoschPointtSensor(BoschPointtEntity, SensorEntity):
    def __init__(self, coordinator, key: str, name: str, device_class, unit, entity_category=None) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_entity_category = entity_category

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class BoschPointtModulationSensor(BoschPointtEntity, SensorEntity):
    _attr_name = "Burner Modulation"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_heat_source_modulation"

    @property
    def native_value(self):
        return burner_modulation(self.coordinator.data)


class BoschPointtNotificationsSensor(BoschPointtEntity, SensorEntity):
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


class BoschPointtZoneStatusSensor(BoschPointtEntity, SensorEntity):
    """Zone status from zones/list (seen: "idle"), plus the gateway's display
    icons (seen: "eco on", "ch off"). Exposed raw so their history shows which
    values appear while heating vs. tapping hot water vs. idle -- the input
    for a reliable hvac_action later."""

    _attr_name = "Zone Status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_zone_status"

    def _zone(self) -> dict:
        for zone in self.coordinator.data.get("zones") or []:
            if zone.get("id") == ZONE_NUMBER:
                return zone
        return {}

    @property
    def native_value(self):
        return self._zone().get("status")

    @property
    def extra_state_attributes(self):
        zone = self._zone()
        return {
            "function_icons": zone.get("functionIcons"),
            "ui_icons": [icon for icon in self.coordinator.data.get("ui_icons") or [] if icon],
        }
