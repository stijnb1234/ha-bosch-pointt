"""Binary sensors for Bosch EasyControl read-only states."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BoschPointtCoordinator
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BoschPointtBinarySensor(
                coordinator, "refill_needed", "Refill Needed", BinarySensorDeviceClass.PROBLEM
            ),
        ]
    )


class BoschPointtBinarySensor(CoordinatorEntity[BoschPointtCoordinator], BinarySensorEntity):
    def __init__(self, coordinator, key: str, name: str, device_class) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get(self._key) == "true"
