"""Number entities for writable Bosch EasyControl settings."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BoschPointtEntity
from .const import DOMAIN, RESOURCE_PATHS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BoschPointtNumber(
                coordinator, "away_mode_temperature", "Away Mode Temperature",
                min_value=5.0, max_value=30.0, step=0.5,
            ),
            BoschPointtNumber(
                coordinator, "open_window_detection_temperature", "Open Window Detection Temperature",
                min_value=5.0, max_value=30.0, step=0.5,
            ),
            BoschPointtNumber(
                coordinator, "sensor_temperature_offset", "Outdoor Sensor Offset",
                min_value=-2.0, max_value=2.0, step=0.5,
            ),
        ]
    )


class BoschPointtNumber(BoschPointtEntity, NumberEntity):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, key: str, name: str, min_value: float, max_value: float, step: float) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.api.put_resource(
            self.coordinator.device_id, RESOURCE_PATHS[self._key], value
        )
        await self.coordinator.async_request_refresh()
