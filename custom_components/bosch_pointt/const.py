"""Constants for the Bosch Pointt integration."""

DOMAIN = "bosch_pointt"

TOKEN_URL = "https://singlekey-id.com/auth/connect/token"
API_BASE = "https://pointt-api.bosch-thermotechnology.com/pointt-api/api/v1"

CLIENT_ID = "BEAE0439-49D3-41B5-83D1-59B0971793F4"

# Optional convenience default for config_flow's refresh_token field --
# entirely optional, the integration is normally set up through the HA UI
# (Settings > Devices & Services > Add Integration), which asks for the
# token directly and validates it against the API before creating the
# entry. secrets_local.py (gitignored) just pre-fills that field so you
# don't have to paste it by hand every time you re-add the integration.
try:
    from .secrets_local import REFRESH_TOKEN
except ImportError:
    REFRESH_TOKEN = None

DEFAULT_SCAN_INTERVAL = 60  # seconds

ZONE_ID = "zn1"
ZONE_NUMBER = 1  # same zone, as numbered in zones/list

RESOURCE_PATHS = {
    "temperature_actual": f"zones/{ZONE_ID}/temperatureActual",
    "temperature_setpoint": f"zones/{ZONE_ID}/temperatureHeatingSetpoint",
    "clock_override": f"zones/{ZONE_ID}/clockOverride/temperatureHeating",
    "user_mode": f"zones/{ZONE_ID}/userMode",
    "outdoor_temp": "system/sensors/temperatures/outdoor_t1",
    "indoor_humidity": "system/sensors/humidity/indoor_h1",
    "firmware_version": "gateway/versionFirmware",
    "away_mode": "system/awayMode/enabled",
    "fireplace_mode": "system/fireplace/enabled",
    "extra_dhw": "dhwCircuits/dhw1/extraDhw",
    "child_lock": "devices/device1/thermostat/childLock/enabled",
    "refill_needed": "heatSources/refillNeeded",
    "hot_water_system": "dhwCircuits/dhw1/hotWaterSystem",
    "system_pressure": "system/appliance/systemPressure",
    "heat_source_modulation": "heatSources/modulation",
    "notifications": "notifications",
    "notification_light": "gateway/notificationLight/enabled",
    "away_mode_temperature": "system/awayMode/temperature",
    "open_window_detection_temperature": "system/openWindowDetection/temperature",
    "sensor_temperature_offset": "system/sensors/temperatures/offset",
    "zones": "zones/list",
    "ui_icons": "gateway/ui/icons",
    "heating_control": "heatingCircuits/hc1/control",
}
