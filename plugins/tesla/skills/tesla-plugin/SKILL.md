---
name: tesla-plugin
description: Use for ANY question about the user's car, vehicle, or Tesla — charge level, range, climate, location, alerts, service, software, nearby chargers, charging history, warranty. Uses the Fermix Tesla plugin, never the browser.
---

# Tesla

The `tesla_*` tools read the owner's car through Tesla's Fleet API. Use them for anything about this car; do NOT use the browser or `web_search`, and never quote a Tesla app screenshot back as live data.

## VIN workflow

Tesla addresses cars by **VIN**, not by name.

- `tesla_list_vehicles` → each car's `vin`, `display_name`, and `state`. Call it **once** per session and reuse the VIN for every other tool.
- `state` is the cloud's view of the car: `online` answers live requests, `asleep` answers only after a wake, `offline` has no connection at all.
- One car on the account: use it. Several: name them and ask which one.

## Pick the tool

Cloud reads — answer even while the car sleeps, and no live request is made:

- `tesla_get_vehicle_status` — online / asleep / offline for one car.
- `tesla_get_fleet_status` — firmware, command-protocol requirement, virtual key pairing, telemetry version.
- `tesla_get_mobile_access` — whether Allow Mobile Access is on (off explains many failures).
- `tesla_get_service_status`, `tesla_get_release_notes`, `tesla_get_vehicle_options`, `tesla_get_warranty`.

Live reads — the car must be awake, and each call is billed:

- `tesla_get_vehicle_data`, one `section` per question:
  - `charge_state` — battery percent, range, charge limit, charging state, time to full, charge port.
  - `climate_state` — inside and outside temperature, climate on/off, seat and steering heaters.
  - `vehicle_state` — odometer, locks, open doors and windows, tyre pressure, software version, sentry mode.
  - `vehicle_config` — trim, paint, wheels, roof, badging.
  - `closures_state` — doors, windows, trunk, frunk.
  - `gui_settings` — the units the car itself displays.
  - `charge_schedule_data`, `preconditioning_schedule_data` — scheduled charging and preconditioning.
- `tesla_get_vehicle_location` — where the car is right now.
- `tesla_get_nearby_charging_sites` — Superchargers and destination chargers near the car.

History:

- `tesla_list_charging_history` — Tesla-billed charging sessions with fees.

Ask for the one section that answers the question. Do not fetch `vehicle_state` to answer "how charged is it".

## Asleep cars

A `408`, "vehicle unavailable", or a timeout on a live read means the car is asleep or offline. It is not an error in the plugin and not a reason to retry.

- Report the last cloud state instead: "it's asleep; Tesla last saw it at <time>".
- **Never wake a car to answer a read.** Sleep is how the battery lasts.
- If `tesla_wake_vehicle` is listed, offer it ("I can wake it, which Tesla bills; want me to?") and call it only after the user says yes. If it is not listed, the owner has not enabled waking; say so rather than retrying.
- After a wake, re-check `tesla_get_vehicle_status` until it reads `online`, then do the live read once. Waking takes a few seconds and can fail.

## Cost

Every call is metered on the owner's Tesla developer account, and live reads of the car are the ones worth rationing.

- One section per question. Two questions about charge and climate are two calls, and that is the ceiling, not a poll.
- Never loop or poll. Do not "refresh" a value the user did not ask to refresh.
- `tesla_get_vehicle_location` and `tesla_get_nearby_charging_sites` are billed live reads too.
- Cloud reads and charging history answer while the car sleeps and disturb nothing; a wake costs about ten times a read, which is why it needs a yes.

## Units and freshness

- Timestamps are epoch **milliseconds**; `gps_as_of` is epoch **seconds**. Convert before reporting, and never print a raw epoch.
- Temperatures are Celsius. Tyre pressure is bar. Odometer and every range field are miles, whatever the car's own display units say.
- A live read is a snapshot from the car's last report, not a live feed. Report the timestamp with the value: "62%, as of 18:04".
- Never invent a value the response did not contain, and never fill a missing number with zero.

## Charging history

- `tesla_list_charging_history` covers Tesla-billed sessions (Supercharging and paid destination charging). It does **not** include home or third-party charging, so it is not the car's total energy use. Say so when the user asks "how much have I spent charging".
- Fees are per session and carry a currency. Sum per currency and report each separately; never add two currencies together.
- Default to the first page. Page only when the user asks for more history.

## Errors

- **401** — the connection expired. Tell the user to reconnect Tesla on the Fermix setup page. Do not loop.
- **403** — either a scope the owner did not grant or a virtual key that is not paired with the car. Say which one the response points to; `tesla_get_fleet_status` shows the pairing.
- **408** — the car is asleep or offline. See Asleep cars.
- **412** — the operator's domain is not registered for this region. Setup work, not something to retry.
- **421** — the account belongs to the other region. The owner fixes `region` in the Tesla OAuth settings.
- **429** — rate limited (Tesla allows 60 data requests, 30 commands, and 3 wakes a minute per car). Wait for the reset the response names; do not retry immediately.
- If the `tesla_*` tools are not listed at all, the plugin is not connected. Say so; never fall back to the browser.

## Not supported (don't claim these)

Starting or stopping charging, setting the charge limit or amps, climate and preconditioning control, locks, horn, lights, windows, trunks, sentry mode, navigation, valet, software updates, energy products (Powerwall, solar, Wall Connector), and telemetry history. Reads and an optional wake are the whole surface. If the user asks for one of these, say it is not available yet rather than describing how the Tesla app does it.
