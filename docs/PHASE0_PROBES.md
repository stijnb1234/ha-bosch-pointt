# Phase 0 probe runbook

Answers the open questions in `HEATING_PLAN.md` §14. Write every result into that table (and anything surprising into
the plan section it affects).

**Prerequisite**: `bosch_pointt` 0.3.0 installed in HA (copy `custom_components/bosch_pointt/` or update via HACS, then
restart). New in 0.3.0:

- actions `bosch_pointt.get_resource` / `bosch_pointt.put_resource` (Developer Tools → Actions; tick **Return
  response** to see the full API JSON);
- `binary_sensor.burner_active`, `sensor.zone_status` (diagnostic, with `ui_icons` attribute),
  `sensor.heating_control` (diagnostic).

All probes go through HA's own session. **Don't run `pointt_client.py` with HA's refresh token.** Tokens rotate on
every use, so a second consumer of the same token logs HA out.

`put_resource` writes straight to the thermostat, bypassing all entity logic. Each write probe below says how to undo
it.

---

## P0 — Save the current EasyControl program (rollback reference)

```yaml
action: bosch_pointt.get_resource
data:
  path: programs/pg1/week
```

Paste the full `value` list into `HEATING_PLAN.md` appendix A.

## P6 — Allowed values of `heatingCircuits/hc1/control` (read only)

```yaml
action: bosch_pointt.get_resource
data:
  path: heatingCircuits/hc1/control
```

Record `value` and `allowedValues` (if present). **Don't write this resource.**

## P1 — Which resource holds the manual-mode setpoint?

1. Try discovery first. Directory paths often list their children:

   ```yaml
   action: bosch_pointt.get_resource
   data:
     path: zones/zn1
   ```

   Also try `zones`, `heatingCircuits/hc1`, `system`. Save anything that looks like a child list.
2. Try the likely candidate:

   ```yaml
   action: bosch_pointt.get_resource
   data:
     path: zones/zn1/manualTemperatureHeating
   ```

3. If neither finds it: capture the Bosch app with mitmproxy (same setup as the original API capture):

   ```bash
   BOSCH_MITM_OUT=bosch_flows.txt mitmdump -s mitm_dump_bosch.py
   ```

   In the app, switch to manual mode and change the temperature once. Look for the `PUT` in `bosch_flows.txt`
   (credentials are redacted by default). Switch the app back to program mode afterwards.

## P3 — How does a dial change appear in the API?

Do this in **both** modes, ~5 min apart.

1. Clock mode (current): turn the dial +0.5 °C. After ≤ 1 min, GET:
   `zones/zn1/clockOverride/temperatureHeating`, `zones/zn1/temperatureHeatingSetpoint`, `zones/zn1/userMode`.
2. Manual mode:

   ```yaml
   action: bosch_pointt.put_resource
   data:
     path: zones/zn1/userMode
     value: manual
   ```

   Turn the dial +0.5 °C, then GET `zones/zn1/userMode`, `zones/zn1/temperatureHeatingSetpoint` and the P1 resource.
3. Undo: `put_resource zones/zn1/userMode clock` and turn the dial back.

## P2 — Does the manual setpoint persist?

Only after P1. Pick an evening when a steady temperature is fine.

1. `put_resource zones/zn1/userMode manual`, then `put_resource <P1 resource> 18.0`.
2. Check the setpoint after 1 h, 6 h and the next morning (`climate.thermostat` history is enough).
3. Optional: take the EasyControl off its wall plate for 10 s (reboot), put it back, and check again.
4. Undo: `put_resource zones/zn1/userMode clock`.

## P4 — Latency: write → burner firing

1. Note the living-room temperature (`climate.thermostat` current temperature), e.g. 19.5.
2. Write actual + 2 (clock mode, known to work):

   ```yaml
   action: bosch_pointt.put_resource
   data:
     path: zones/zn1/clockOverride/temperatureHeating
     value: 21.5
   ```

3. Note the time. Watch `binary_sensor.burner_active` in history; record the delay until it turns on.
4. Undo: try `put_resource zones/zn1/clockOverride/temperatureHeating 0`. Record whether that cancels the override
   (setpoint returns to the program value). If not, write the program's current value instead.

Combine with the underfloor diagnosis (plan §10) on a day the floor is cold: same write, but keep it ~2 h.

## P5 — Heating vs. hot water vs. idle

Watch `sensor.zone_status` (state + `ui_icons` / `function_icons` attributes) and `binary_sensor.burner_active` in three
situations. Record the values in each:

| Situation | Zone status | ui_icons | Burner active |
|---|---|---|---|
| Idle (setpoint below room temp, no tap) | | | |
| Heating (during P4) | | | |
| Hot-water tap only (heating idle, open a hot tap 2 min) | | | |

The goal is a signal that says "heating" but not during a hot-water tap. That becomes `hvac_action` in 0.4.0.

## P7 — TRV external temperature (Bedroom Stijn, Z2M `0xf84477fffe05bd8c`)

1. In Z2M → device → *Exposes*, confirm `external_temperature` is listed. In HA, check whether a
   `number.…_external_temperature` entity exists. If it does, test that first; otherwise use MQTT:

   ```yaml
   action: mqtt.publish
   data:
     topic: zigbee2mqtt/0xf84477fffe05bd8c/set
     payload: '{"external_temperature": 15.0}'
   ```

   (Replace the topic's device part with the friendly name if you renamed it in Z2M.)
2. With the TRV setpoint at ~20 °C, push 15.0 → `pi_heating_demand` should rise within minutes. Push 25.0 → it should
   drop to 0. Record what `local_temperature` shows (TRV sensor or the pushed value?).
3. Timeout: push 12.0 once, then stop. Check every 10 min for 2 h when the TRV goes back to its own sensor
   (`pi_heating_demand` / `local_temperature` change). Record the timeout, or "none within 2 h". If there's none, the
   plan needs a keep-alive and an explicit fallback.

## P8 — TRV firmware and reporting

1. Shelly app (Bluetooth, near the TRV): read the firmware version and update to ≥ 1.5.0. Zigbee OTA isn't supported.
2. Z2M → device → *Reporting*: for `hvacThermostat` / `pi_heating_demand`, set min 10 s, max 300 s, change 1. Same
   for `localTemp` if missing.
3. Check that `sensor.…_pi_heating_demand` updates at least every 5 min in HA history.

## P9 — Automatic bypass valve

At the boiler/piping, look for a valve connecting flow and return with a spring cap or setting knob
(*overstortventiel* / automatic bypass). Photograph it and its setting. Also check the TrendLine II installation manual
or ask the installer whether the boiler has an internal bypass.
