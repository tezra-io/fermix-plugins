---
name: tesla-plugin
description: Use for ANY question or instruction about the user's car, vehicle, or Tesla: charge, range, climate, location, alerts, service, software, chargers, charging history, warranty, and commands (charging, climate, locks, Sentry, lights, navigation). Uses the Fermix Tesla plugin, never the browser.
---

# Tesla

The `tesla_*` tools read the owner's car through Tesla's Fleet API. Use them for anything about this car; do NOT use the browser or `web_search`, and never quote a Tesla app screenshot back as live data.

## VIN workflow

Tesla addresses cars by **VIN**, not by name.

- `tesla_list_vehicles` → each car's `vin`, `display_name`, and `state`. Call it **once** per session and reuse the VIN for every other tool.
- `state` is the cloud's view of the car: `online` answers live requests, `asleep` answers only after a wake, `offline` has no connection at all.
- One car on the account: use it. Several: name them and ask which one.
- The VIN is a tool argument, not conversation. Never print it, or any part of it, in a reply; call the car by its `display_name` or "your Tesla". Give the VIN only if the user asks for it outright.

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
- If `tesla_wake_vehicle` is listed, offer it ("I can wake it, which Tesla bills; want me to?") and call it only after the user says yes. If it is not listed, the owner has not turned commands on; say so rather than retrying.
- After a wake, re-check `tesla_get_vehicle_status` until it reads `online`, then do the live read once. Waking takes a few seconds and can fail.

## Commands

This section applies only when `tesla_*` command tools are listed. If they are not, the owner has not turned commands on: say so, and do not describe the Tesla app's steps as a workaround.

Every command moves a real car that someone may be standing next to.

- **Confirm every single command before sending it.** State the exact action and the car it goes to — "start charging on the Model 3, VIN 5YJ…1234?" — and wait for a clear yes. A yes to one command is not a yes to the next one: never chain commands off a single confirmation, and ask again even when the user's request implies several.
- If the car is asleep, offer `tesla_wake_vehicle` first and get its own yes. It is under the same switch as the commands, so if commands are listed, waking is available.
- Send one command, report what came back, then stop. Do not follow a command with a read the user did not ask for.

### Reading the result

- A result with `result: false` is **the car refusing**, not a failure to reach it. Report the `reason` the car gave in plain words ("it says the charge port is closed") and **never retry** — the answer will not change until the condition does.
- An error saying the car did not confirm the command means the outcome is **unknown**: it may have applied. Do not resend. Read the relevant state first (`tesla_get_vehicle_data` with the section that would have changed, or `tesla_get_vehicle_status` if the car may have dropped offline) and tell the user what you actually find.
- A `403` on a command usually means the virtual key is not paired with this car. `tesla_get_fleet_status` shows the pairing; pairing is the owner's job, done once per car from the Tesla app.

### Access changes

`tesla_unlock_doors` and turning Sentry Mode off with `tesla_set_sentry_mode` change who can get into the car. Do not fold them into a larger request. Name the change on its own — "this unlocks the car and leaves it unlocked" — and get a yes for that specific thing.

### Never offer these

PIN to Drive, valet mode, speed limits, and parental controls are not available through this plugin at all. Say so; do not approximate them with another command.

## When a command says the car is asleep

- That refusal comes from the car's command channel and outranks the cloud list: `tesla_list_vehicles` can still say `online` for minutes after the car has dozed off.
- Do not re-check the list. Call `tesla_wake_vehicle` (harmless if the car is already awake), then read `tesla_get_vehicle_status` until it says `online`, then send the same command once more, with the user's original yes still standing. Ask again only if the wake is billed and the user has not agreed to waking.
- If the second attempt is refused the same way, stop and say so; do not loop.

## Cost

Every call is metered on the owner's Tesla developer account, and live reads of the car are the ones worth rationing.

- One section per question. Two questions about charge and climate are two calls, and that is the ceiling, not a poll.
- Never loop or poll. Do not "refresh" a value the user did not ask to refresh.
- `tesla_get_vehicle_location` and `tesla_get_nearby_charging_sites` are billed live reads too.
- Cloud reads and charging history answer while the car sleeps and disturb nothing; a wake costs about ten times a read, which is why it needs a yes.
- Commands are billed too, at their own rate. That is a reason to send exactly the one the user asked for, never a reason to skip the confirmation.

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

Changing scheduled charging or preconditioning (the schedules can be read, not set), media and volume, trunk and frunk, windows, seat and steering-wheel heaters, HomeLink, software updates, PIN to Drive, valet mode, speed limits, parental controls, energy products (Powerwall, solar, Wall Connector), and telemetry history. If the user asks for one of these, say it is not available rather than describing how the Tesla app does it.
