# Bosch EasyControl (Pointt API) for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/github/manifest-json/v/stijnb1234/ha-bosch-pointt?filename=custom_components%2Fbosch_pointt%2Fmanifest.json)

Home Assistant integration for the **Bosch EasyControl**thermostats that talk to Bosch's **Pointt REST API**.

## Features

| Platform        | Entities                                                                                                                           |
|-----------------|------------------------------------------------------------------------------------------------------------------------------------|
| `climate`       | Thermostat: current/target temperature, clock (auto) / manual mode                                                                 |
| `sensor`        | Outdoor Temperature, Indoor Humidity, Firmware Version, Hot Water System, System Pressure, Burner Modulation, Active Notifications |
| `switch`        | Away Mode, Fireplace Mode, Child Lock, Extra Hot Water*, Notification Light                                                        |
| `binary_sensor` | Refill Needed, Burner Active                                                                                                       |
| diagnostic      | Zone Status (with display icons), Heating Control                                                                                  |
| `number`        | Away Mode Temperature, Open Window Detection Temperature, Outdoor Sensor Offset                                                    |

All entities are grouped under a single "Bosch EasyControl" device.

\* disabled by default if your system's domestic hot water setup doesn't support it (reported as `used: false` by the
API).

Not exposed by this API: raw boiler-internal telemetry (flow/return temps, boiler-level fault codes) that older Nefit
Easy integrations had. See
[Known limitations](#known-limitations).

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ (top right) → **Custom repositories**.
2. Add this repository URL, category **Integration**.
3. Search for "Bosch EasyControl" in HACS and install.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/bosch_pointt/` into `<config>/custom_components/`.
2. Restart Home Assistant.

## Setup

The integration is fully UI-driven — no YAML.

1. **Get a refresh token** (see below).
2. Settings → Devices & Services → **Add Integration** → search "Bosch EasyControl (Pointt API)".
3. Paste the refresh token. The integration validates it against the API and auto-discovers your device — no serial
   number needed.

The token rotates on every use; the integration persists the new value into the config entry automatically, so this is
normally a one-time step. You only need to repeat it if the token gets fully revoked (e.g. you change your Bosch account
password).

### Getting a refresh token

Bosch's login form requires solving an hCaptcha, so this can't be scripted end-to-end — you log in normally through your
own browser, and only the final code-for-tokens exchange is scripted.

```
python pointt_login.py
```

This opens the SingleKey ID login page (the same login the official app uses). Log in as usual — your password only ever
goes to the real
`singlekey-id.com`, never to this script or Home Assistant. After login, the browser tries to follow a
`com.bosch.rrc://...` link and fails (expected — that's the app's custom URL scheme). Open DevTools (F12) → Network tab,
find that failed request, copy its full URL, and paste it into the script's prompt when asked. It exchanges the
authorization code for tokens and writes the refresh token to `pointt_credentials.json`.

> That redirect URL contains a short-lived, one-time authorization code —
> don't share, log, or post it anywhere. Treat `pointt_credentials.json` the
> same way afterward: it holds a live, working (if narrowly-scoped) refresh
> token for your Bosch account.

## Actions (advanced)

For API exploration and debugging, the integration registers two raw actions (Developer Tools → Actions):

- `bosch_pointt.get_resource` — `path: zones/zn1/userMode` → returns the full API response (value, `writeable`,
  allowed values, ...). Directory paths such as `zones/zn1` may list their children.
- `bosch_pointt.put_resource` — `path` + `value` → writes straight to the thermostat, bypassing all entity logic.
  Returns the read-back value when "return response" is enabled.

Paths are restricted to plain resource paths below `/gateways/{id}/resource/`. These actions use the integration's
own session. Don't also run `pointt_client.py` with the same refresh token: tokens rotate on every use, and the
second consumer logs the other one out.

## How it works

- **API**: `https://pointt-api.bosch-thermotechnology.com/pointt-api/api/v1`
  — plain HTTPS/JSON, `GET`/`PUT` on `/gateways/{serial}/resource/{path}`.
- **Auth**: OAuth2 authorization_code + PKCE against SingleKey ID, using the official app's own `client_id`.
  `offline_access` scope means the resulting refresh token is long-lived and self-renews on every use.
- The integration polls all known resource paths every 60s via a single
  `DataUpdateCoordinator` and persists the rotated refresh token back into the config entry.

Full endpoint/response reference (redacted): [`bosch_api_reference.txt`](bosch_api_reference.txt).

## Known limitations

- No boiler-internal telemetry (flow/return temperature, KM-bus-style fault codes) — not exposed anywhere in the API.
  `heatSources/modulation`
  (burner %) and `system/appliance/systemPressure` are the closest equivalents; `notifications` is the real cause-code
  equivalent.
- If the refresh token is fully revoked, there's no in-HA recovery flow — re-run `pointt_login.py` and re-add the
  integration with the new token.
- Only compile-checked and tested against one real EasyControl CT200 unit — other EasyControl hardware/firmware may
  expose slightly different resource paths.

## Other files in this repo

These support development/debugging and aren't needed to just run the integration:

- **`pointt_client.py`** — standalone script using the same API client logic without Home Assistant, for quick manual
  checks.
- **`mitm_dump_bosch.py`** — mitmproxy addon used to originally capture the API from the official app; useful again if
  Bosch changes the API. `mitmdump -s mitm_dump_bosch.py`; output file via `BOSCH_MITM_OUT`, credentials redacted
  unless `BOSCH_MITM_RAW=1`.
- **`archive_legacy_xmpp/`** — the original (dead-end) XMPP investigation that led to discovering the Pointt API. Kept
  for the reasoning trail.

## Security notes

- `pointt_credentials.json` and `custom_components/bosch_pointt/secrets_local.py`
  hold live credentials and are gitignored — never commit them.
- The refresh token is scoped to gateway read/write for one device, not full account access, but still worth protecting
  like a password.

## Credits

- [ha-bosch-buderus-heating's setup guide](https://github.com/SoftwareSchmied/ha-bosch-buderus-heating/blob/main/docs/setup.md)
  for the browser-login + scripted-token-exchange technique.
- [homeassistant-nefit-easy](https://github.com/RaimondB/homeassistant-nefit-easy)
  as the reference for the older, now-incompatible XMPP protocol.
