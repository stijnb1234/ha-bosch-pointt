"""The Bosch Pointt (EasyControl) integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import PointtApi, PointtAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, RESOURCE_PATHS

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "sensor", "switch", "binary_sensor", "number"]


class BoschPointtCoordinator(DataUpdateCoordinator):
    """Polls the Pointt REST API for the resources we care about."""

    def __init__(self, hass: HomeAssistant, api: PointtApi, device_id: str, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.device_id = device_id
        self.entry = entry

    async def _async_update_data(self):
        data = {}
        try:
            for key, path in RESOURCE_PATHS.items():
                resp = await self.api.get_resource(self.device_id, path)
                data[key] = resp.get("value") if resp else None
        except PointtAuthError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001 - surface any transport error to the coordinator
            raise UpdateFailed(f"Error communicating with Pointt API: {err}") from err

        # Persist a rotated refresh token so it survives restarts.
        if self.api.refresh_token != self.entry.data.get("refresh_token"):
            self.hass.config_entries.async_update_entry(
                self.entry, data={**self.entry.data, "refresh_token": self.api.refresh_token}
            )
        return data


class BoschPointtEntity(CoordinatorEntity[BoschPointtCoordinator]):
    """Base for all Bosch Pointt entities -- groups them under one device."""

    def __init__(self, coordinator: BoschPointtCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name="Bosch EasyControl",
            manufacturer="Bosch",
            model="EasyControl",
            sw_version=coordinator.data.get("firmware_version") if coordinator.data else None,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = PointtApi(session, entry.data["refresh_token"])
    coordinator = BoschPointtCoordinator(hass, api, entry.data["device_id"], entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
