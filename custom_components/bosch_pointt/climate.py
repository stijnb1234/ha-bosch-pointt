"""Climate entity for the Bosch EasyControl zone."""
from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BoschPointtCoordinator
from .const import DOMAIN, RESOURCE_PATHS

# Confirmed via mitmproxy capture: app PUTs {"value": "clock"} / {"value": "manual"}.
MODE_HA_TO_DEVICE = {HVACMode.AUTO: "clock", HVACMode.HEAT: "manual"}
MODE_DEVICE_TO_HA = {v: k for k, v in MODE_HA_TO_DEVICE.items()}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BoschPointtClimate(coordinator, entry)])


class BoschPointtClimate(CoordinatorEntity[BoschPointtCoordinator], ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = list(MODE_HA_TO_DEVICE.keys())

    def __init__(self, coordinator: BoschPointtCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{coordinator.device_id}_zn1_climate"
        self._attr_name = "Thermostat"

    @property
    def current_temperature(self):
        return self.coordinator.data.get("temperature_actual")

    @property
    def target_temperature(self):
        return self.coordinator.data.get("temperature_setpoint")

    @property
    def hvac_mode(self):
        device_mode = self.coordinator.data.get("user_mode")
        return MODE_DEVICE_TO_HA.get(device_mode, HVACMode.AUTO)

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        await self.coordinator.api.put_resource(
            self.coordinator.device_id, RESOURCE_PATHS["clock_override"], temperature
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        device_mode = MODE_HA_TO_DEVICE.get(hvac_mode)
        if device_mode is None:
            return
        await self.coordinator.api.put_resource(
            self.coordinator.device_id, RESOURCE_PATHS["user_mode"], device_mode
        )
        await self.coordinator.async_request_refresh()
