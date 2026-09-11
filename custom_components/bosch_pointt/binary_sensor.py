"""Binary sensors for Bosch EasyControl read-only states."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BoschPointtEntity, burner_modulation
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BoschPointtBinarySensor(
                coordinator, "refill_needed", "Refill Needed", BinarySensorDeviceClass.PROBLEM
            ),
            BoschPointtBurnerActiveSensor(coordinator),
        ]
    )


class BoschPointtBinarySensor(BoschPointtEntity, BinarySensorEntity):
    def __init__(self, coordinator, key: str, name: str, device_class) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get(self._key) == "true"


class BoschPointtBurnerActiveSensor(BoschPointtEntity, BinarySensorEntity):
    """On while the burner modulates above 0 %. Also on while tapping hot
    water (combi boiler), so on its own it doesn't mean "heating"."""

    _attr_name = "Burner Active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_burner_active"

    @property
    def is_on(self) -> bool | None:
        modulation = burner_modulation(self.coordinator.data)
        if modulation is None:
            return None
        return modulation > 0
