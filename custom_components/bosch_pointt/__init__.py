"""The Bosch Pointt (EasyControl) integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import re

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import PointtApi, PointtAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, RESOURCE_PATHS

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "sensor", "switch", "binary_sensor", "number"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_GET_RESOURCE = "get_resource"
SERVICE_PUT_RESOURCE = "put_resource"

# Plain resource paths only (e.g. "zones/zn1/userMode"): no "..", no query
# string -- the debug services must not reach anything outside
# /gateways/{id}/resource/.
_RESOURCE_PATH = re.compile(r"^[A-Za-z0-9_]+(/[A-Za-z0-9_]+)*$")


def _resource_path(value) -> str:
    path = cv.string(value).strip().strip("/")
    if not _RESOURCE_PATH.match(path):
        raise vol.Invalid(f"invalid resource path: {value}")
    return path


def _resource_value(value):
    if isinstance(value, bool):
        # Pointt models booleans as the strings "true"/"false".
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return value
    raise vol.Invalid("value must be a number or a string")


GET_RESOURCE_SCHEMA = vol.Schema({vol.Required("path"): _resource_path})
PUT_RESOURCE_SCHEMA = vol.Schema(
    {vol.Required("path"): _resource_path, vol.Required("value"): _resource_value}
)


def burner_modulation(data: dict) -> float | None:
    """heatSources/modulation returns a stringArray, e.g. ["70", "0"] -- first
    element is current burner modulation %. Second element's meaning is
    unconfirmed (always seen as "0" so far)."""
    value = data.get("heat_source_modulation")
    if not value:
        return None
    try:
        return float(value[0])
    except (TypeError, ValueError, IndexError):
        return None


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
                data[key] = await self._get_value(path)
        except PointtAuthError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001 - surface any transport error to the coordinator
            raise UpdateFailed(f"Error communicating with Pointt API: {err}") from err

        self.persist_refresh_token()
        return data

    async def _get_value(self, path: str):
        try:
            resp = await self.api.get_resource(self.device_id, path)
        except aiohttp.ClientResponseError as err:
            if err.status == 404:
                # Not every EasyControl firmware exposes every resource --
                # one missing path shouldn't fail the whole poll.
                _LOGGER.debug("Resource %s not available (404)", path)
                return None
            raise
        return resp.get("value") if resp else None

    def persist_refresh_token(self) -> None:
        """Persist a rotated refresh token so it survives restarts."""
        if self.api.refresh_token != self.entry.data.get("refresh_token"):
            self.hass.config_entries.async_update_entry(
                self.entry, data={**self.entry.data, "refresh_token": self.api.refresh_token}
            )


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the raw resource services (debugging / API exploration)."""

    def get_coordinator() -> BoschPointtCoordinator:
        coordinators = hass.data.get(DOMAIN)
        if not coordinators:
            raise ServiceValidationError("Bosch EasyControl is not set up")
        return next(iter(coordinators.values()))

    async def get_resource(call: ServiceCall) -> ServiceResponse:
        coordinator = get_coordinator()
        path = call.data["path"]
        try:
            resp = await coordinator.api.get_resource(coordinator.device_id, path)
        except (aiohttp.ClientError, PointtAuthError) as err:
            raise HomeAssistantError(f"GET {path} failed: {err}") from err
        finally:
            coordinator.persist_refresh_token()
        if isinstance(resp, dict):
            return resp
        return {"value": resp}

    async def put_resource(call: ServiceCall) -> ServiceResponse:
        coordinator = get_coordinator()
        path, value = call.data["path"], call.data["value"]
        _LOGGER.info("put_resource %s = %r", path, value)
        resp = None
        try:
            await coordinator.api.put_resource(coordinator.device_id, path, value)
            if call.return_response:
                # Read back what the gateway reports now. May still show the
                # old value if the device hasn't applied the write yet.
                resp = await coordinator.api.get_resource(coordinator.device_id, path)
        except (aiohttp.ClientError, PointtAuthError) as err:
            raise HomeAssistantError(f"PUT {path} failed: {err}") from err
        finally:
            coordinator.persist_refresh_token()
        await coordinator.async_request_refresh()
        if not call.return_response:
            return None
        return resp if isinstance(resp, dict) else {"value": resp}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_RESOURCE,
        get_resource,
        schema=GET_RESOURCE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PUT_RESOURCE,
        put_resource,
        schema=PUT_RESOURCE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


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
