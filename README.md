# Bosch EasyControl (CT200 B) debugging notes

Started as "decryption errors connecting via XMPP", ended with a fully
working REST API client and a Home Assistant integration. Notes below so
future-me (or anyone else hitting this) doesn't redo the investigation.

## TL;DR

Firmware `05.04.00` (device: EasyControl CT200 B, HW10) dropped the old
XMPP + AES-ECB protocol entirely. `bosch-thermostat-client` (and every
XMPP-based fork/integration, including the reference
[homeassistant-nefit-easy](https://github.com/RaimondB/homeassistant-nefit-easy))
talks to a transport this device no longer speaks. It's not a credentials
bug, not a library bug -- Bosch moved the backend.

The real thing now: a plain HTTPS REST API
(`pointt-api.bosch-thermotechnology.com`) secured with OAuth2 (SingleKey
ID), used by the official app via `okhttp`. No AES, no XMPP, just JSON.

## How we found this

1. Reproduced the XMPP decrypt failures locally (`bosch_thermostat_client`
   0.28.2, matches upstream issue
   [#542](https://github.com/bosch-thermostat/home-assistant-bosch-custom-component/issues/542)
   exactly -- same firmware, same lib version, same `bosch_cli` repro).
2. Verified the AES key-derivation algorithm itself was correct (matches
   upstream source, matches a manual test script) -- ruled out a code bug.
3. Confirmed the *access key + password* combo was correct too (see
   `archive_legacy_xmpp/` for the old investigation -- key derivation
   script, brute-forced variant checks, all consistent, all still garbage
   output). Not a credentials problem either.
4. MITM'd the real EasyControl Android app with mitmproxy to see what it
   actually talks to. Had to patch the app (`apk-mitm`, since Android
   doesn't trust user-installed CAs by default from API 24+) and spoof the
   Play Store installer ID (app has an installer-source check). Found: the
   app never even connects to the old XMPP host (`xmpp.rrcng.ticx.boschtt.net`)
   -- it's all `pointt-api.bosch-thermotechnology.com` now.

## The real protocol

- **Device API**: `https://pointt-api.bosch-thermotechnology.com/pointt-api/api/v1`
- **Auth**: OAuth2 authorization_code + PKCE against SingleKey ID
  (`https://singlekey-id.com/auth`), same pattern as a standard Duende
  IdentityServer deployment.
  - `client_id`: `BEAE0439-49D3-41B5-83D1-59B0971793F4` (the app's own,
    reused here)
  - Token endpoint: `https://singlekey-id.com/auth/connect/token`
  - Scopes include `pointt.gateway.list`, `pointt.gateway.resource.rrcng.app`,
    `offline_access`, etc.
  - **The login form requires solving an hCaptcha.** That's a deliberate
    anti-automation gate -- we don't script past it. Instead: log in
    through your own real browser (you solve the captcha normally, same as
    always), then script only the code-for-tokens exchange. See "Getting a
    refresh token" below. `offline_access` scope means the resulting
    `refresh_token` is long-lived and self-renews (rotates) on every use.
- **Resources**: `GET/PUT /gateways/{serial}/resource/{path}`, e.g.
  `/gateways/101273687/resource/zones/zn1/temperatureActual`. Values come
  back as `{"id", "type", "value", "writeable", "unitOfMeasure", ...}`.
  PUT body is just `{"value": ...}`.
- Most string-typed togglables use `"true"`/`"false"` as literal strings,
  not JSON booleans (confirmed from real captures). `extraDhw` is the one
  oddball using `"on"`/`"off"`.
- Full endpoint list with real example responses: **`bosch_api_reference.txt`**
  (redacted -- no tokens/cookies/passwords, just paths and shapes).

## Getting a refresh token (no proxy needed)

We originally got the first `refresh_token` by MITM'ing the app with
mitmproxy (see "How we found this" -- that was for *discovering* the API in
the first place, endpoints and all). For just obtaining/renewing a token
once you already know the API, there's a much simpler way -- credit to
[ha-bosch-buderus-heating's setup guide](https://github.com/SoftwareSchmied/ha-bosch-buderus-heating/blob/main/docs/setup.md)
for the technique: **do the login in your own real browser**, and only
script the final code-for-tokens exchange. No proxy, no rooted phone, no
patched APK.

Run:
```
venv/Scripts/python.exe pointt_login.py
```

It opens the SingleKey ID login page in your browser (same login as the
app -- solve the captcha normally, enter your password only on the real
`singlekey-id.com` page, never into this script or Home Assistant). After a
successful login, the browser tries to navigate to a `com.bosch.rrc://...`
link and fails (expected -- that's the app's custom URL scheme, no desktop
app handles it). Open DevTools (F12) → Network tab, find that failed
request, copy its full URL, and paste it into the script's prompt. It
extracts the authorization `code`, exchanges it for tokens, and writes a
fresh `refresh_token` to `pointt_credentials.json`.

**That redirect URL contains a short-lived, one-time authorization code --
don't share it, log it, or post it anywhere.** Same caution applies to
`pointt_credentials.json` itself afterward (see Security notes).

Update `custom_components/bosch_pointt/const.py`'s `REFRESH_TOKEN` with the
same value if you're running the HA integration's hardcoded-token setup.

## Gaps vs. the old Nefit Easy integration

No boiler-internal telemetry (flow/return/supply temperature, cause/fault
codes as raw boiler codes) turned up anywhere in ~1800 captured requests
across multiple app sessions. `system/appliance/systemPressure` and
`heatSources/modulation` (burner %) are the closest equivalents and are
real, live values. `notifications` (`type: errorList`) is the actual
cause-code equivalent -- just empty because nothing's currently faulted.
Best guess: EasyControl's Pointt API abstracts at the zone/system level and
genuinely doesn't expose the old KM-bus-style boiler internals Nefit Easy
had.

## Files in this folder

- **`custom_components/bosch_pointt/`** -- the Home Assistant integration
  (see below).
- **`pointt_client.py`** -- minimal standalone script, same API client
  logic without HA. Good for quick manual checks:
  `venv/Scripts/python.exe pointt_client.py`
- **`pointt_login.py`** -- one-time (or whenever-needed) login helper: real
  browser login + scripted code-for-tokens exchange. See "Getting a refresh
  token" below. This is the normal way to (re-)obtain a token now -- the
  mitmproxy/APK-patching setup was only needed for the original API
  discovery.
- **`pointt_credentials.json`** -- `client_id` + `refresh_token`. **This is
  a live credential for the Bosch account** -- treat it like a password.
  Rotates automatically on use (both `pointt_client.py` and the HA
  integration persist the new value after every refresh).
- **`bosch_api_reference.txt`** -- redacted endpoint/response reference,
  extracted from the mitmproxy capture.
- **`mitm_dump_bosch.py`** -- the mitmproxy addon used for capturing (dumps
  full request/response for any `bosch`/`singlekey` host to a text file).
  Reusable if the API changes again or more endpoints need discovering:
  `venv/Scripts/mitmdump.exe --listen-host 0.0.0.0 --listen-port 8080 --set tcp_hosts='.*boschtt\.net' -s mitm_dump_bosch.py`
- **`easycontrol-patched.apks`** -- the patched EasyControl APK bundle
  (cert pinning disabled, trusts mitmproxy's CA, debug-signed). Lets you
  redo a MITM capture without re-running `apk-mitm` from scratch:
  ```
  # extract and install (phone connected via adb, USB debugging on):
  cd apk_patched_reinstall && unzip -o ../easycontrol-patched.apks
  adb uninstall com.bosch.tt.bosch.controlng
  adb install-multiple -i com.android.vending base.apk split_config.*.apk
  ```
- **`archive_legacy_xmpp/`** -- the original (dead-end but instructive) XMPP
  investigation: manual AES key-derivation script, algorithm-variant brute
  force, old device pairing credentials (access key/password from the QR
  code -- separate from the SingleKey ID account password), a backup of the
  unpatched XMPP connector, and the original `connect_test.py`. Not useful
  for this device anymore, but keeps the reasoning trail if a future
  firmware/device needs it, or if you want to see how we ruled everything
  else out first.

## The Home Assistant integration (`custom_components/bosch_pointt/`)

Install: copy the folder into `<ha config>/custom_components/`, restart HA,
add via Settings → Devices & Services → Add Integration → "Bosch
EasyControl (Pointt API)".

**Auth is hardcoded** (`const.py`: `CLIENT_ID`, `REFRESH_TOKEN`,
`DEVICE_ID`) -- personal-use shortcut, no in-HA login flow. Config flow just
confirms/creates the single entry; no form beyond an optional device ID
override. The refresh token rotates on every poll and the new value is
written back into the config entry automatically (`__init__.py`), so it
survives HA restarts -- you should basically never need to touch `const.py`
again after first setup, unless the token gets fully revoked (e.g. you
change your Bosch password). If that happens: run `pointt_login.py` (see
"Getting a refresh token" above) and update `const.py` with the new value.

### Entities

| Platform | Entity | Notes |
|---|---|---|
| `climate` | Thermostat | current/target temp, clock/manual mode (both confirmed against real app traffic) |
| `sensor` | Outdoor Temperature, Indoor Humidity | |
| `sensor` | Firmware Version, Hot Water System | informational |
| `sensor` | System Pressure | bar, real appliance-level reading |
| `sensor` | Burner Modulation | % from `heatSources/modulation` |
| `sensor` | Active Notifications | count + raw list attribute; equivalent of "cause codes", currently always 0 (no faults seen) |
| `switch` | Away Mode, Fireplace Mode, Child Lock | |
| `switch` | Extra Hot Water | disabled by default -- not available on this system's DHW setup (`used: false` in the API) |
| `switch` | Notification Light | wall unit LED toggle |
| `binary_sensor` | Refill Needed | |
| `number` | Away Mode Temperature, Open Window Detection Temperature, Outdoor Sensor Offset | writable settings, not in the reference integration |

### Architecture

- `api.py` -- `PointtApi`: token refresh (lazy, cached until near-expiry)
  + thin GET/PUT wrappers. Raises `PointtAuthError` if the refresh token is
  ever rejected outright.
- `__init__.py` -- one `DataUpdateCoordinator` polling every 60s, fetching
  all resource paths in `const.RESOURCE_PATHS` in one pass. Persists a
  rotated refresh token back into the config entry.
- `climate.py` / `sensor.py` / `switch.py` / `binary_sensor.py` /
  `number.py` -- thin `CoordinatorEntity` wrappers reading from
  `coordinator.data[key]`.

### Known caveats

- Only compile-checked (`python -m py_compile`), never run inside a real
  Home Assistant instance -- no HA install in this sandbox. Watch the logs
  on first real load for import-path mismatches (already fixed two:
  `AddEntitiesCallback` not `AddEntityCallback`, `PRECISION_HALVES` lives in
  `homeassistant.const` not `homeassistant.components.climate.const`).
- `HVACMode.HEAT -> "manual"` / `HVACMode.AUTO -> "clock"` -- confirmed via
  a real PUT captured from the app (`{"value": "manual"}` /
  `{"value": "clock"}`), not a guess.
- If the refresh token ever dies (revoked, password changed, or Bosch
  changes the token lifetime policy), there's no in-HA recovery flow --
  run `pointt_login.py` again and manually update `const.py`.

## Security notes from this session

- An early debug capture briefly wrote the real SingleKey ID account
  password to disk in plaintext (login form POST body, captured before we
  realized the addon should filter to API traffic only). That capture file
  has been deleted. **The password should already have been rotated** as
  flagged during the session -- if not, do that.
- `pointt_credentials.json` holds a live, working refresh token. Don't
  commit it anywhere public. It's scoped to gateway read/write for this one
  device, not full account access, but still worth protecting.
- The patched APK (`easycontrol-patched.apks`) has certificate pinning
  disabled and an embedded trust for mitmproxy's CA -- fine for your own
  debugging device, don't distribute it.
