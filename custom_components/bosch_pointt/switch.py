"""Switch entities for Bosch EasyControl toggles.

Device values are strings, not JSON booleans (confirmed via mitmproxy:
GET returns e.g. {"value": "false"}, PUT expects {"value": "true"}).
extraDhw uses "on"/"off" instead of "true"/"false".
"""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BoschPointtCoordinator
from .const import DOMAIN, RESOURCE_PATHS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BoschPointtSwitch(coordinator, "away_mode", "Away Mode", "true", "false"),
            BoschPointtSwitch(coordinator, "fireplace_mode", "Fireplace Mode", "true", "false"),
            BoschPointtSwitch(coordinator, "child_lock", "Child Lock", "true", "false"),
            # Not available/used on every installation (e.g. instant/combi DHW
            # systems) -- entity_registry_enabled_default off, enable manually
            # if your system actually has this circuit.
            BoschPointtSwitch(coordinator, "extra_dhw", "Extra Hot Water", "on", "off", enabled_default=False),
            BoschPointtSwitch(coordinator, "notification_light", "Notification Light", "true", "false"),
        ]
    )


class BoschPointtSwitch(CoordinatorEntity[BoschPointtCoordinator], SwitchEntity):
    def __init__(self, coordinator, key: str, name: str, on_value: str, off_value: str, enabled_default: bool = True) -> None:
        super().__init__(coordinator)
        self._key = key
        self._on_value = on_value
        self._off_value = off_value
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_entity_registry_enabled_default = enabled_default

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get(self._key) == self._on_value

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.api.put_resource(
            self.coordinator.device_id, RESOURCE_PATHS[self._key], self._on_value
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.api.put_resource(
            self.coordinator.device_id, RESOURCE_PATHS[self._key], self._off_value
        )
        await self.coordinator.async_request_refresh()
