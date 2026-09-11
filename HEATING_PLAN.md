# Smart Heating Plan – Nefit TrendLine II + EasyControl + Home Assistant + Shelly TRVs

_Last revised: 2026-09-11 (fresh re-evaluation; supersedes the earlier VTherm / 30-min-guard design)._

## 1. Goal

Comfortable, reliable heating control where:

- existing **Nefit Bosch TrendLine II HRC30 CW5** boiler stays;
- physical **Bosch EasyControl** in the living room stays as the household's physical thermostat and the only link to
  the boiler;
- **Home Assistant is the brain**: it owns all schedules, per-room targets, presence, modes and central heat demand;
- radiators per room controlled by **Shelly BLU TRVs coupled directly to Zigbee2MQTT** (no gateway);
- underfloor heating eventually gets smart (pre-heat) control too;
- system stays simple enough for the whole household;
- manual control (TRV knob, EasyControl dial) always remains possible and is respected;
- external room temperature sensors are the source of truth per room;
- phone geolocation (HA companion app) drives presence;
- start small, expand only after each step is proven;
- every failure (HA, cloud, Zigbee, sensor) degrades to "house stays reasonably warm", never "cold" or "runaway hot".

Core design choice: **don't change everything at once**. Prove one radiator/room first, then expand.

---

## 2. Current installation

**Boiler**: Nefit Bosch TrendLine II HRC30 CW5 (combi, instant DHW), EMS bus. EasyControl talks to it directly over EMS.

**Thermostat**: Bosch EasyControl CT200 (API reports `RRC 2.0`, firmware 05.04.00), physically in the living room.
Facts from the Pointt API (see `bosch_api_reference.txt`):

- one zone (`zn1`), one heating circuit (`hc1`);
- `hc1/control = room` — boiler is **room-temperature led**: it only fires when the EasyControl setpoint is above the
  living-room temperature it measures, and flow temperature scales with that difference;
- currently `userMode = clock` with a weekly program; `clockOverride/temperatureHeating` is a temporary override on top
  of the program (reads `0.0` when no override is active). Target state: `userMode = manual`, no program (D2);
- burner modulation (`heatSources/modulation`) is readable → we can see whether the boiler actually fires;
- cloud polling only (Pointt REST API, 60 s poll), no local API.

**Radiators** (6 total):

| Room          | Count | Current state   | Plan                                          |
|---------------|------:|-----------------|-----------------------------------------------|
| Living room   |     2 | Old dial valves | Replace valve bodies, then 2 TRVs (phase 2)   |
| Office        |     1 | Needs fitting   | Shelly BLU TRV (phase 4)                      |
| Bedroom Stijn |     1 | **TRV fitted**  | **Phase 1 test room** (Z2M `0xf84477fffe05bd8c`) |
| Bedroom PM    |     1 | Ready/to verify | Shelly BLU TRV (phase 5)                      |
| Bedroom G     |     1 | Ready/to verify | Shelly BLU TRV (phase 5)                      |

**Sensors**: ESPHome temperature sensor in Bedroom Stijn, already in HA.

**Underfloor heating**: 1 loop kitchen, 1 loop bathroom, shared manifold, pump switched on by a pipe-temperature/time
control, limiter dial on the manifold caps floor water temp. Feels insufficient — living room/radiators warm while the
floor lags. Needs diagnosis before automating (§10).

**Home Assistant**: mini-PC, Zigbee2MQTT present, this repo's `bosch_pointt` integration installed and working
(read + `climate.set_temperature`).

---

## 3. Desired daily behavior

**Winter weekdays (office day)**: living room ~19 °C morning/evening, not all day, lower at night.

**WFH days / weekends**: living room ~19 °C during day and evening; office and/or Bedroom Stijn warm while in use;
office drops in the evening.

**Bedrooms**: lower than living/office; no heating when their occupant isn't home.

**Away** (everyone out): setback everywhere; pre-heat when someone heads home.

Must run automatically; manual override must always stay easy and **hold until the next relevant scheduled moment**.

---

## 4. Decisions (2026-09-11)

| # | Decision | Why |
|---|----------|-----|
| D1 | **HA decides everything; the TRV regulates the valve.** HA pushes the room sensor value into the TRV's `external_temperature` and sets its target; Shelly's own algorithm (fw ≥ 1.4 "adaptive heating control") moves the valve. | HA stays the brain for *what* and *when*. The TRV handles *how*, locally: fewer motor moves and less Zigbee traffic, better battery life. If HA/Zigbee dies, the TRV falls back to its own sensor and last target instead of freezing a valve position. |
| D2 | **HA owns every schedule, including the living room. EasyControl runs in `manual` mode with no program**; HA writes its single manual setpoint (§6.5). | One place for all logic; allows presence/WFH/pre-heat smartness EasyControl can't do. A program kept as fallback would reset HA's override at every switch point (heating dips, burner cycling, missed dial changes) and be a second source of truth the household could edit. |
| D3 | **Central heat-demand logic lives in the `bosch_pointt` integration**, not in YAML. | The integration is the only component that knows what *it* wrote vs. what a human dialled. That gives exact manual-override detection, rate limiting, restart safety and unit tests. |
| D4 | **EasyControl dial = living-room target.** A hand-dialled value becomes the living target until the next living-room schedule transition; bumping for other rooms pauses 10 min, then resumes on top of it. | Matches what the person meant ("I want the living room warmer/cooler") without starving other rooms. |
| D5 | **HA writes room targets only at transitions** (schedule edge, mode change, presence change, HA start), never continuously. | A manual change (TRV knob, dashboard, dial) then naturally holds until the next transition. That is the "until next scheduled moment" rule, with no override bookkeeping per room. |
| D6 | **Living-room TRVs are required** before the system is considered complete (phase 2, right after phase 1). | Room-led boiler control means every bedroom heat request raises the EasyControl setpoint above living-room temp. Without living TRVs, the living room overshoots whenever another room calls for heat. |
| D7 | Native HA building blocks only (schedule helpers, `person`, blueprints, one package) + our integration. No Versatile Thermostat / Better Thermostat. | VTherm/BT regulate by offsetting the TRV setpoint, which conflicts with D1's external-temperature push (double regulation). The TRV exposes no `running_state`, so their central-boiler features would get a poor "is heating" signal. Our needs beyond D1 are schedules + presence, which HA does natively. |
| D8 | EMS-ESP not now. Route stays: HA → `bosch_pointt` → Pointt cloud → EasyControl → EMS → boiler. | Proven to fire the boiler. EMS-ESP stays the fallback (§16) and an optional read-only telemetry tool for the underfloor diagnosis. |

---

## 5. Target architecture

```text
 person.* (GPS)   schedule.* helpers   input_select.heating_mode   ESPHome/Zigbee room sensors
        │                 │                     │                            │
        └─────────────────┴──────────┬──────────┴────────────────────────────┘
                                     ▼
                     HA "room zone" blueprint (one instance per room)
                     computes target on transitions only (D5)
                                     │
             ┌───────────────────────┼─────────────────────────────┐
             ▼                       ▼                             ▼
   Bedroom/office TRVs      Living-room target               ext-temp push automation
   (Z2M: setpoint +         = climate.thermostat             (room sensor → TRV
    external_temperature)     (bosch_pointt "intended          external_temperature)
             │                 target", D4)
             │                       │
   pi_heating_demand %               │ living TRVs follow intended target (phase 2)
             │                       │
             └──────────┬────────────┘
                        ▼
        bosch_pointt demand controller (§6)
        effective EasyControl setpoint = intended target,
        or bumped above living-room actual when another zone demands heat
                        │ Pointt cloud (manual setpoint)
                        ▼
                  EasyControl ──EMS──► Nefit TrendLine II ──► radiators + underfloor
```

**Responsibilities**

- **Room zone blueprint (HA)**: per-room target from schedule × house mode × occupancy; writes only on transitions.
- **External-temp push (HA)**: keeps each TRV fed with the real room temperature.
- **Shelly TRVs**: local valve regulation to the target using the pushed room temperature; manual knob; reports
  `pi_heating_demand` (valve opening = heat demand).
- **`bosch_pointt`**: holds the living-room *intended target*, detects manual dial changes, aggregates demand from all
  zones, and translates it into the EasyControl setpoint the boiler needs.
- **EasyControl**: physical dial + display, the boiler's controller; runs in manual mode, HA sets its setpoint.
- **Underfloor**: slow zone; becomes a time-based demand source (pre-heat) once diagnosed.

---

## 6. Central heat demand (the core mechanism)

### 6.1 Problem

The boiler only fires when EasyControl's setpoint > living-room temperature. A cold bedroom with a wide-open TRV gets no
hot water if the living room is satisfied. So heat demand from any zone must be turned into
"EasyControl setpoint above living-room actual".

### 6.2 Two setpoints, not one

The integration separates:

- **intended target** — what the living room *should* be (written by the HA schedule, or by a human on the dial / in
  HA). Shown as `climate.thermostat`'s target temperature. Restored across HA restarts.
- **effective setpoint** — what is actually written to EasyControl (its manual-mode setpoint). Equals the intended
  target unless a bump is needed. Exposed as an attribute + diagnostic sensor.

### 6.3 Demand controller algorithm (runs on every poll and on demand-source changes, debounced 30 s)

```text
demand   = max over configured sources (TRV pi_heating_demand %, binary sources on = 100 %; unavailable = ignored)
active   = hysteresis: on at demand ≥ 15 %, off at demand ≤ 5 % — and only after ≥ 10 min on (anti short-cycle)

if control disabled or not active or manual_pause:
    effective = intended_target
else:
    delta     = min_delta + (max_delta − min_delta) × demand / 100        # 0.5 … 2.0 °C
    effective = clamp(round_up_0.5(living_actual + delta), intended_target, max_setpoint)

write effective as EasyControl manual setpoint only if it differs from the last write
and (≥ 2 min since last write, or effective == intended_target)   # releases are never delayed
```

- As the living room warms during a bump, `living_actual + delta` creeps up and the controller re-bumps, bounded by
  `max_setpoint`. Living TRVs (phase 2) keep the living room itself at its intended target.
- A bigger `delta` means a hotter flow temperature (room-led control), so demand % maps to heating speed.
- All thresholds are live-tunable `number` entities (phase 1 tuning), with the defaults above.

### 6.4 Manual dial detection (D4)

Each poll the integration compares EasyControl's current setpoint and mode with its own last write:

| Observation | Interpretation | Action |
|---|---|---|
| setpoint ≠ last write (±0.25), > 90 s after our write | human dialled / used Bosch app | intended target = dialled value; pause bumping 10 min; fire `bosch_pointt_manual_change` event |
| `userMode` ≠ `manual` | someone switched EasyControl to program mode | switch back to `manual`, re-assert effective setpoint, notify |
| matches last write | our own value | nothing |

The manual value then lasts until the living-room zone blueprint writes its next transition (D5), which is "the next
scheduled moment" in HA's schedule.

### 6.5 EasyControl in manual mode (no program)

EasyControl runs `userMode = manual`. HA writes one persistent manual setpoint; nothing on the device changes it by
itself. No switch points, no resets, no second schedule to conflict with HA.

Trade-off: no self-reset if HA/cloud dies. EasyControl then keeps the last written value:

- **not bumping at that moment** → the living room stays at its last target. Other rooms only get heat when the living
  room calls. The house stays warm, and TRV rooms regulate locally.
- **bumping at that moment** → the setpoint stays at most `max_setpoint` (21 °C phase 1, 22 °C later). Before phase 2
  the living room can drift up to that; from phase 2 the living TRVs still hold the living room at target, so the only
  cost is a boiler that keeps supplying heat the TRVs throttle.
- The household can always turn the dial down by hand, just like a normal thermostat.
- The integration writes the intended target (releases any bump) on unload/shutdown and when
  `switch.heat_demand_control` is turned off, so a planned HA restart never leaves a bump behind.

Before switching: note the current program (`programs/pg1/week`) in this document so it can be restored if the project
is ever rolled back.

### 6.6 Heat sink

The boiler must always have somewhere to dump heat when a single bedroom TRV is the only open valve.

- Phase 1: the living-room radiators (old dial valves) stay open, turned down, as the sink.
- Phase 0 checks whether the installation has an automatic bypass valve (overstortventiel).
- Phase 2 decision: bypass present → living TRVs may close fully. No bypass → integration/automation keeps one living
  TRV at ≥ 20–30 % (`valve_position`, manual mode) while a bump is active.

The underfloor loop is a second sink once its pump runs.

---

## 7. Room zones (TRV rooms)

### 7.1 External temperature push

- Automation (blueprint `trv_external_temperature`): on room-sensor change (throttled to ≤ 1 per min) + a heartbeat every
  10 min → write the TRV's `external_temperature` (Z2M expose, write-only; via `number.set_value` or
  `mqtt.publish zigbee2mqtt/<trv>/set {"external_temperature": x}`, whichever works in P7).
- Sensor unavailable → stop pushing → TRV falls back to its internal sensor (timeout verified in P7) + notification.
- TRV settings: `system_mode: heat`, `manual_mode: false`, `local_temperature_calibration: 0`, setpoint limits 5–24 °C,
  calibration run after mounting, firmware ≥ 1.5.0 (updates only via Shelly app/Bluetooth, not Zigbee OTA).

### 7.2 Room zone blueprint

Inputs: target entity (TRV climate(s), or `climate.thermostat` for the living room), comfort/eco/away temperatures
(`input_number`), one `schedule` helper per day type (office day / WFH / weekend-holiday; on = comfort), occupant
`person`s (optional; bedrooms), house mode.

```text
target = off/frost  if heating_mode == off
       = away       if heating_mode == away or (room has occupants and none home)
       = comfort    if today's schedule is on
       = eco        otherwise
```

Triggers (= "relevant moments"): schedule on/off, day-type change, heating-mode change, occupant presence change,
temperature helper change, HA start. It writes only then (D5).

### 7.3 Living room

- Target entity = `climate.thermostat` (the integration's intended target). The same blueprint writes it.
- Phase 2: follower automation sets both living TRVs to the intended target. External temp = EasyControl
  `temperatureActual` (or a dedicated sensor).
- Living TRVs are **not** demand sources. EasyControl already sees living-room demand natively.

---

## 8. Manual control

| Action | Meaning | Holds until |
|---|---|---|
| Turn a TRV knob | new target for that room | next transition of that room's zone |
| Turn the EasyControl dial | new living-room target; bumps pause 10 min | next living-room transition |
| Change a zone in the HA dashboard | same as knob | next transition |
| House mode (away / holiday / off) | global | changed back, or presence logic |
| Boost button (later) | comfort for 1 h | timer |

Heat for other rooms keeps working during a manual living-room change (after the 10 min pause). The EasyControl display
then shows the bumped value, which the household should know about.

---

## 9. Presence and house modes

- `input_select.heating_mode`: `auto` / `away` / `holiday` / `off`.
- Day type: `binary_sensor.workday` (NL holidays) + `input_boolean.wfh_today`. WFH auto-sets on a workday when Stijn is
  still home at 08:45, resets 03:00; manual toggle wins.
- Away: all `person`s not home ≥ 20 min → `away`. Return: HA `proximity` "approaching and < N km" → back to `auto`
  (pre-heat). Everyone home → `auto`.
- Bedrooms use their occupant's `person` state (D7 blueprint input).

---

## 10. Underfloor heating: diagnose first, then automate

Complaint: living room/radiators warm, floor still cold. Understand why before compensating in software.

**Test while floor is cold, living room already warm** (use the phase-0 debug service or dial to raise EasyControl):

1. Raise EasyControl setpoint ~2 °C above living-room actual.
2. Confirm boiler fires (`Burner Modulation` > 0).
3. Confirm the pipe to the manifold gets warm.
4. Confirm the underfloor pump runs, and note after how long.
5. Check flow/return temps (touch/IR thermometer; clamp sensors on the manifold if needed).
6. Confirm both loops flow.
7. Observe floor over 30–120 min; note when it becomes noticeably warmer.

Goal: **distinguish a control problem from a hydraulic problem.** Candidates: pump starts too late/runs too short,
water temp too low, manifold limiter too low, low flow, air in a loop, imbalance, boiler stops once the living room is
satisfied (room-led control — very likely a big factor), boiler stops delivering too soon.

**If mainly timing** (expected): the floor becomes a *binary demand source* for the integration. A `schedule` helper
per day type turns on `pre-heat` ~2 h before comfort time (starting estimate, refined from measurements). While on,
the controller bumps EasyControl so the boiler keeps delivering, even when the living room is satisfied. Plus a manual
"prepare underfloor" boost button.

**If hydraulic**: fix first (bleed, limiter, pump timer, balancing) — no software workaround.

---

## 11. Failure modes

| Failure | Effect | Mitigation |
|---|---|---|
| HA down | TRVs keep last target; external temp times out → internal sensor; EasyControl keeps last manual setpoint (≤ `max_setpoint`) | `max_setpoint` cap, release on shutdown, TRV local regulation, dial by hand (§6.5) |
| Pointt cloud / internet down | writes fail; EasyControl keeps last manual setpoint | integration state `error` + HA notification; retry each poll |
| Refresh token revoked | as cloud down | HA repair issue; re-run `pointt_login.py` |
| TRV / Zigbee offline | that room's demand ignored; TRV still regulates locally | notification on unavailable > 30 min |
| Room sensor offline | push stops → TRV internal sensor | notification |
| Controller bug / runaway | bounded by `max_setpoint`, min write interval | `switch.heat_demand_control` off = pure passthrough |
| All valves closed during bump | boiler without sink | §6.6 bypass / min-open rule |
| DHW tap during heating | modulation > 0 not caused by heating | don't use modulation alone as `hvac_action` (P5) |

---

## 12. `bosch_pointt` integration changes

**0.3.0 — probes & read-only additions (phase 0)** — _implemented 2026-09-11 (services, zone status + display icons,
heating control, burner active, per-resource 404 tolerance, token persisted after every service call)._

- Services `bosch_pointt.get_resource(path)` / `bosch_pointt.put_resource(path, value)` (advanced/debug). Probes run
  through HA's own session. **Never run `pointt_client.py` with HA's refresh token**: tokens rotate on use, so a second
  consumer of the same chain logs HA out. For CLI probes, do a separate `pointt_login.py` login.
- Poll extra resources: `zones/list` (status), `gateway/ui/icons`, `heatingCircuits/hc1/control`.
- `binary_sensor.burner_active`.
- Deferred to 0.4.0 (they depend on probe results): polling the manual-mode setpoint resource and writing it from
  climate `set_temperature` when `userMode = manual` (P1/P3); `hvac_action` on the climate entity (P5).

**0.4.0 — demand controller (phase 1)**

- `demand.py`: pure-Python state machine (§6.3/6.4), no HA imports → unit-tested with pytest (TDD).
- Climate entity: target = intended target (`RestoreEntity`), attributes `effective_setpoint`, `target_source`
  (`schedule`/`manual`/`restored`), `demand`, `bump_active`, `manual_pause_until`.
- Options flow: demand source entities (entity selector: `sensor` %, `binary_sensor`, `input_boolean`, `schedule`).
- Entities: `switch.heat_demand_control`, `binary_sensor.central_heat_demand`, `sensor.heat_demand` (%),
  `sensor.demand_controller_state` (`idle`/`bumping`/`manual_pause`/`disabled`/`error`), tuning `number`s (thresholds,
  min/max delta, `max_setpoint`, manual pause).
- Enforce `userMode = manual` (§6.4).
- Unload / controller disabled → write intended target (release bump).
- HA integration tests with `pytest-homeassistant-custom-component` for restart/restore and manual detection.

## 13. HA configuration in this repo

```text
homeassistant/
  packages/heating.yaml                       # heating_mode, wfh_today, per-room input_numbers, workday, proximity
  blueprints/automation/heating/
    room_zone.yaml                            # §7.2
    trv_external_temperature.yaml             # §7.1
    living_room_trv_follower.yaml             # §7.3 (phase 2)
```

Schedule helpers are created in the HA UI, since the household edits them there. Their entity ids go in the blueprint
instances. The trashed `automations_slaapkamer_stijn.yaml` is superseded by the integration's demand controller.

---

## 14. Probes to answer in phase 0 (record results here)

Step-by-step instructions: [`docs/PHASE0_PROBES.md`](docs/PHASE0_PROBES.md).

| # | Question | How | Result |
|---|---|---|---|
| P1 | Which resource holds the manual-mode setpoint (likely `zones/zn1/manualTemperatureHeating`)? | mitmproxy (`mitm_dump_bosch.py`) while changing temperature in the Bosch app in manual mode | |
| P2 | Does the manual setpoint persist indefinitely (hours, EasyControl reboot/power cycle, cloud reconnect)? | set, observe over 48 h | |
| P3 | How does a physical dial change in manual mode appear in the API (same resource? `userMode` unchanged?) | turn dial, `get_resource` | |
| P4 | Latency PUT → burner firing | timestamps, modulation | |
| P5 | `zones/list` `status` values when heating vs. DHW tap vs. idle | observe | |
| P6 | Allowed values of `hc1/control` (read only, don't write yet) | GET full response | |
| P7 | TRV `external_temperature`: accepted via HA entity or MQTT? Does `pi_heating_demand` react? Fallback timeout when pushes stop (radiator mode)? What does `local_temperature` show? | push values, stop pushing | |
| P8 | TRV firmware version; `pi_heating_demand` reporting interval (configure Z2M reporting if > 5 min) | Shelly app (BLE), Z2M | |
| P9 | Automatic bypass valve present in the installation? | inspect boiler/piping | |

---

## 15. Phased implementation plan

### Phase 0 — Verify & prepare (no automation live)

1. Integration 0.3.0 (§12): debug services, extra read-only resources, burner sensor. _Code done; deploy to HA._
2. Run probes P1–P9, fill in §14. Adjust §6 wherever a probe contradicts an assumption.
3. Underfloor diagnosis (§10); photograph manifold/pump/limiter setting.
4. TRV: firmware ≥ 1.5.0, calibration, settings per §7.1.
5. Record the current EasyControl program in this document (rollback reference). Don't switch to manual mode yet.

**Exit**: all probes answered, and the boiler is proven to fire reproducibly on an HA-written setpoint.

### Phase 1 — Bedroom Stijn end-to-end (+ living room schedule in HA)

1. External-temp push: ESPHome sensor → Bedroom Stijn TRV. Run 48 h; check the TRV regulates on room temp.
2. `packages/heating.yaml` + `room_zone` blueprint. Instances: Bedroom Stijn (TRV) and living room
   (`climate.thermostat`). Switch EasyControl to `manual` mode at the same moment the living-room instance goes live,
   so HA takes over the living schedule.
3. Integration 0.4.0 demand controller (TDD), source = Bedroom Stijn `pi_heating_demand`. Phase-1 `max_setpoint` 21 °C;
   living dial valves turned down as sink (§6.6).
4. Presence: Stijn's `person`, away/return, WFH auto-detection.
5. Test scenarios:
   - cold bedroom evening, living satisfied → boiler fires, bedroom reaches target, bump releases;
   - bedroom demand at night while living is on eco;
   - EasyControl dial change during a bump → becomes living target, 10 min pause, holds until next transition;
   - TRV knob change → holds until next transition;
   - HA restart mid-bump → intended target restored, no spurious "manual";
   - disable `switch.heat_demand_control` → release;
   - ESPHome sensor unplugged → TRV fallback + notification;
   - everyone leaves / returns.
6. Tune thresholds/deltas for 2 weeks; record living-room overshoot and bedroom heat-up time.

**Exit**: 2 weeks without intervention, demand works reproducibly, manual overrides behave per §8, household OK with
the EasyControl display behavior.

### Phase 2 — Living room TRVs

1. Replace the 2 old valve bodies with TRV-compatible ones (plumber).
2. 2 Shelly TRVs, follower automation (§7.3), external temp from EasyControl actual.
3. Decide heat-sink rule from P9 (§6.6); raise `max_setpoint` to 22 °C.

**Exit**: during bedroom bumps the living room stays within +0.5 °C of its target.

### Phase 3 — Underfloor heating

Per the §10 outcome: hydraulic fixes first, or a pre-heat schedule as a binary demand source + boost button. Measure
floor warm-up time and refine the lead time.

### Phase 4 — Office

TRV + sensor + zone instance with WFH schedule; add it as a demand source.

### Phase 5 — Bedrooms PM and G

TRVs + sensors + zone instances tied to their occupants' presence; add as demand sources.

### Phase 6 — Optimization (only if useful)

Learned pre-heat times, proximity-based pre-heat, window detection (temperature-drop or contact sensors),
energy dashboard from `energy/history`, weather-compensated `hc1/control` experiment (P6: may remove the need for bumps
entirely once all rooms have TRVs), EMS-ESP only if the Pointt route proves unreliable.

---

## 16. Deliberately not doing (for now)

Replacing EasyControl; Bosch Smart Home; tado X; Versatile/Better Thermostat (D7); EMS-ESP (D8); new manifold; buying
all TRVs at once; automating anything before it's manually tested.

**Fallback if the Pointt route proves unreliable**: EMS-ESP gateway on the EMS bus. The CT200 has known write
limitations there, so it needs its own design. EasyControl may stay as the physical interface.

---

## Appendix A. EasyControl program before switching to manual mode (rollback reference)

_Fill in from probe P0 (`bosch_pointt.get_resource` → `programs/pg1/week`)._

```json
```
