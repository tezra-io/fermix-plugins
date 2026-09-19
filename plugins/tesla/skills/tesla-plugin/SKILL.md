---
name: tesla-plugin
description: Use for ANY question or instruction about the user's car, vehicle, or Tesla: charge, range, climate, location, alerts, service, software, chargers, charging history, warranty, and commands (charging, climate, seats, locks, trunk, windows, Sentry, lights, navigation). Uses the Fermix Tesla plugin, never the browser.
---

# Tesla

The `tesla_*` tools are the only way to this car. Never use the browser or `web_search` for it; the one exception is looking up a destination's street address.

## The VIN

- Every tool except `tesla_list_vehicles` takes `vin`. If a VIN already appears earlier in this conversation (any tool result), reuse it and do not list again. Only when no VIN is in the conversation, call `tesla_list_vehicles` once.
- One car on the account: use it. Several: ask which.
- Never print the VIN or any part of it. Call the car by its `display_name` or "your Tesla".

## Arguments

The tool list already names each tool's arguments; do not call `tool_describe`.

- `vin` only: status, location, fleet status, mobile access, alerts, service, options, warranty, wake, start/stop charging, open/close charge port, start/stop climate, lock, unlock, vent windows, close windows, flash lights, honk.
- `tesla_get_vehicle_data`: `vin`, `section` = `charge_state` (battery %, range, limit, charging, time to full) | `climate_state` (inside/outside temperature, climate on/off) | `vehicle_state` (odometer, locks, doors, windows, tyres, software, Sentry) | `vehicle_config` (trim, paint, wheels) | `closures_state` | `gui_settings` | `charge_schedule_data` | `preconditioning_schedule_data`. One section per question.
- `tesla_get_release_notes`: `vin`, `staged` (bool). `tesla_get_nearby_charging_sites`: `vin`, `count` (1-25), `radius` (miles, 1-200). `tesla_list_charging_history`: `vin`, `start_time`, `end_time` (ISO 8601 with offset), `page_no`, `page_size` (1-50).
- `tesla_set_charge_limit`: `vin`, `percent` (50-100). `tesla_set_charging_amps`: `vin`, `amps` (1-48). `tesla_set_cabin_temperature`: `vin`, `driver_celsius` (15-28), optional `passenger_celsius`. `tesla_set_preconditioning_max`, `tesla_set_sentry_mode`, `tesla_set_steering_wheel_heater`: `vin`, `enabled` (bool).
- `tesla_set_seat_heater`: `vin`, `seat`, `level` (0 off, 1 low, 2 medium, 3 high). `seat` is `front_left` | `front_right` | `rear_left` | `rear_center` | `rear_right` | `rear_left_back` | `rear_right_back` | `third_row_left` | `third_row_right`. `tesla_set_seat_cooler`: the same, `front_left` and `front_right` only. `tesla_set_auto_seat_climate`: `vin`, `seat` (`front_left` and `front_right` only), `enabled` (bool).
- `tesla_actuate_trunk`: `vin`, `which` = `front` (opens only) | `rear` (toggles). `tesla_set_vehicle_name`: `vin`, `name` (1-32 characters).
- Navigation. Coordinates: `tesla_navigate_to`, `vin`, `latitude`, `longitude`. An address: `tesla_send_navigation`, `vin`, `destination` (a full street address with city, the place name may lead it), `timestamp_ms` (now, epoch milliseconds, as a string), optional `locale` (default `en-US`). A route of stops: `tesla_navigate_waypoints`, `vin`, `waypoints`, comma-separated `refId:<Google Maps place ID>` entries the user supplies.

## Reads

- Cloud reads (status, fleet status, mobile access, alerts, service, release notes, options, warranty, charging history) answer while the car sleeps and are not billed.
- Live reads (`tesla_get_vehicle_data`, location, nearby chargers) need the car awake and are billed. One call per question; never poll or refresh unasked.
- A live read that fails with 408 or "vehicle unavailable" means asleep or offline: say so with the last cloud state. Never wake a car to answer a read. Offer `tesla_wake_vehicle` only if it is listed and only on the user's yes.

## Commands

Present only while the owner's "Allow vehicle commands" switch is on. If none are listed, say commands are off; do not describe the Tesla app instead.

- A direct request is the consent: "honk my car", "lock the car", "start charging" are sent and reported. No confirmation question.
- Ask first only when the action is implied ("get the car ready"), several commands would be chained, the target car is unclear, or the command is a side effect of another request. Then name the exact command and car and wait for a yes.
- Never send a command the user did not ask for. One command, one report, then stop.
- `result: false` is the car refusing; report its `reason` and do not retry. An error that the car did not confirm means the outcome is unknown: read the relevant state, do not resend.
- Refused as asleep: that outranks the cloud list, which lags. Do not re-list. Call `tesla_wake_vehicle`, read `tesla_get_vehicle_status` until `online`, send the same command once more. Refused twice: stop and say so.
- Unlock and Sentry off change who can enter the car. A direct request is still the consent; afterwards say what it leaves ("unlocked until you lock it").
- Seat heating, seat cooling and the steering wheel heater need climate on. On a direct request send `tesla_start_climate` first, then the setting, and report both. Cooling is the front seats only.
- Trunk and windows move parts of the car. A direct request is still the consent: name what will move ("the rear trunk", "the windows"), then send it. `front` opens the frunk and never closes it; `rear` toggles, so say which way you expect it to go.
- `tesla_set_vehicle_name` renames the car in the app. It is a rename, not a control: nothing on the car moves.
- A navigation send sets the destination on the car's screen; it does not drive the car. Say the address that was sent.
- The car resolves only a full street address. A bare place name ("the barber shop") or a link you composed lands as unreadable text or a wrong place, and still reports `result: true`. When the user names a place without an address, find the address first: `web_search` the name with the user's city (ask for the city if the conversation does not give it; never search with the car's coordinates). Several matches: ask which. Then send `<place name>, <street address>, <city>, <region>`. A Google Maps share link is fine only when the user pasted it.

## Errors

401 sign in again on the setup page. 403 scope not granted or key not paired (`tesla_get_fleet_status` shows pairing; pairing is the owner's job in the Tesla app). 412 domain not registered for the region. 421 wrong region in the sign-in client. 429 rate limited; wait for the reset. Never fall back to the browser.

## Units

Timestamps are epoch milliseconds (`gps_as_of` seconds): convert them. Celsius, bar, miles. A live read is a snapshot: report its time with the value. Never invent or zero-fill a missing value. Charging history is Tesla-billed sessions only, not home charging; sum fees per currency.

## Not available

Sunroof, the steering wheel heater's level and its automatic mode (on and off are covered), upcoming calendar entries, setting charge or precondition schedules, media, HomeLink, software updates, PIN to Drive, valet, speed limits, parental controls, energy products, telemetry history. Say so; do not approximate with another command.
