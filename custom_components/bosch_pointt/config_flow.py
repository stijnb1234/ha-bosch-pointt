"""Config flow for Bosch Pointt.

Fully UI-driven: asks for a refresh token (pre-filled from
secrets_local.py if you've set that up, otherwise blank -- get one by
running pointt_login.py, see README.md), validates it by calling the API,
and auto-discovers the device id from GET /gateways so you never have to
type a serial number by hand.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PointtApi, PointtAuthError
from .const import DOMAIN, REFRESH_TOKEN


class BoschPointtConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bosch Pointt."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            token = user_input["refresh_token"].strip()
            session = async_get_clientsession(self.hass)
            api = PointtApi(session, token)
            try:
                gateways = await api.get_gateways()
            except PointtAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001 - surface any transport error as a generic failure
                errors["base"] = "cannot_connect"
            else:
                if not gateways:
                    errors["base"] = "no_gateways"
                else:
                    device_id = gateways[0]["deviceId"]
                    await self.async_set_unique_id(device_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Bosch EasyControl",
                        data={
                            "device_id": device_id,
                            # api.refresh_token, not the input value -- the
                            # get_gateways() call above may have already
                            # rotated it.
                            "refresh_token": api.refresh_token,
                        },
                    )

        schema = vol.Schema(
            {vol.Required("refresh_token", default=REFRESH_TOKEN or ""): str}
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
