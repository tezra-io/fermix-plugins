# Changelog

## 1.1.1

- The "not paired" refusal no longer sends the owner to pair the Fermix
  project's own key. It named `https://tesla.com/_ak/fermix.ai`, which pairs the
  key published on fermix.ai: a car paired that way still refused this
  operator's commands, and the holder of that key's private half gained a key
  to the car. The sentence now gives `https://tesla.com/_ak/<your-domain>` and
  says which domain that is: the one the operator's own Tesla application
  registered and that serves its public key. A test keeps any fixed host out of
  it.
- README: the origin example is `https://example.com` rather than fermix.ai, the
  pairing step uses `<your-domain>` and warns against pairing a domain you do
  not control, and the command rules match the shipped skill: a direct request
  is the consent, and the agent asks first only for an implied, chained or
  ambiguous command.

## 1.1.0

- Comfort commands through the helper: `tesla_set_seat_heater` and
  `tesla_set_seat_cooler` set one seat to 0 (off), 1 (low), 2 (medium) or
  3 (high) — nine seat positions for heat, the two front seats for cooling —
  `tesla_set_auto_seat_climate` hands a front seat back to the car, and
  `tesla_set_steering_wheel_heater` turns the wheel heater on or off. The car
  refuses all four while climate is off, so the skill turns climate on first.
- Closures through the helper: `tesla_actuate_trunk` opens the front trunk or
  toggles the rear one (open if closed, closed if open and powered), and
  `tesla_vent_windows` and `tesla_close_windows` move the windows. These move
  parts of the car, so the skill names what will move before it sends them.
- `tesla_set_vehicle_name` renames the car as it appears in the Tesla app. It
  is a rename, not a control: nothing on the car moves.
- Two more navigation tools on the http rail, beside `tesla_navigate_to`,
  because Tesla's SDK routes all three over REST rather than the signed
  protocol: `tesla_send_navigation` sends a full street address
  (`navigation_request`, with the `locale` and `timestamp_ms` Tesla's own
  client sends; the car does not resolve a bare place name, so the skill looks
  the address up first), and `tesla_navigate_waypoints` sends a route of Google Maps
  place IDs (`navigation_waypoints_request`).
- Still not included, and why: navigating to a Supercharger by id
  (`navigation_sc_request`), because `tesla_get_nearby_charging_sites` returns
  no site id to pass it, and upcoming calendar entries, whose payload Tesla
  does not document. Also unchanged: the sunroof, the steering-wheel heater's
  level and its automatic mode, schedules, media, HomeLink, software updates,
  PIN to Drive, valet, speed limits, parental controls, energy products and
  telemetry.
- The eight helper commands sit behind the same `ALLOW_COMMANDS` switch and the
  same signing key as every other command; the two navigation tools are gated
  on the switch as well. Nothing new is asked of the operator.

## 1.0.1

- The mark is Tesla's own: `assets/logo.png` is the 196 pixel favicon
  tesla.com serves for itself
  (`https://www.tesla.com/themes/custom/tesla_frontend/assets/favicons/favicon-196x196.png`,
  retrieved 2026-09-13, sha256
  `c82462c37d740922a2e4dd0f5cc8f4da3d1e646453cfb3c525fae4f34864a6fc`), byte
  for byte. The redrawn SVG it replaces was nobody's official artwork.
- Shorter setting labels: `ALLOW_COMMANDS` reads "Allow vehicle commands" and
  `SIGNING_KEY_PATH` reads "Signing key path". A label is the name of the
  control; what each one means stays in this README.

## 1.0.0

- Initial release: declarative http-rail reads plus a vendored local helper for
  signed vehicle commands.
- 15 read tools: `tesla_list_vehicles`, `tesla_get_vehicle_status`,
  `tesla_get_vehicle_data`, `tesla_get_vehicle_location`,
  `tesla_get_fleet_status`, `tesla_get_mobile_access`,
  `tesla_get_vehicle_alerts`, `tesla_get_service_status`,
  `tesla_get_release_notes`, `tesla_get_nearby_charging_sites`,
  `tesla_list_charging_history`, `tesla_get_vehicle_options`,
  `tesla_get_warranty` — and `tesla_wake_vehicle` plus `tesla_navigate_to`,
  which Tesla's own SDK routes over REST rather than the signed protocol.
- 15 command tools through the helper: `tesla_start_charging`,
  `tesla_stop_charging`, `tesla_set_charge_limit`, `tesla_set_charging_amps`,
  `tesla_open_charge_port`, `tesla_close_charge_port`, `tesla_start_climate`,
  `tesla_stop_climate`, `tesla_set_cabin_temperature`,
  `tesla_set_preconditioning_max`, `tesla_lock_doors`, `tesla_unlock_doors`,
  `tesla_set_sentry_mode`, `tesla_flash_lights`, `tesla_honk_horn`.
- `fermix-tesla`, a local MCP server built from `src/` in this repo and shipped
  inside the signed artifact, signs each command with the operator's own
  application key and delivers it end to end to the car. Fermix runs it only
  while commands are allowed and hands it the access token and the key path; it
  holds no credentials of its own. Nothing is downloaded at run time.
- OAuth2 via the operator's own Tesla developer app, with the domain
  registration and published public key Tesla's onboarding requires; scopes
  `openid`, `offline_access`, `vehicle_device_data`, `vehicle_location`,
  `vehicle_charging_cmds`, `vehicle_cmds`.
- Regional by construction: every tool carries the `na` and `eu` Fleet API
  hosts and Fermix picks one from the verified region, so no argument and no
  redirect can move a request. China needs its own application and is excluded.
- Cost-aware by design: Tesla meters every live vehicle read and every wake.
  Cloud reads answer while the car sleeps, live reads take one section per
  call, nothing paginates or polls, and the skill teaches the agent to report a
  sleeping car rather than wake it.
- Commands and waking are off until the operator sets `ALLOW_COMMANDS` to
  `true`; until then not one command tool — nor `tesla_wake_vehicle` — is
  advertised, and the helper is never started. `SIGNING_KEY_PATH` names the
  operator's private key PEM; the key is read by the helper on this machine and
  never copied into config or sent anywhere.
- Every command is confirmed on its own: the skill makes the agent name the
  action and the car and wait for a yes before each one, never chain commands
  off a single yes, treat the car's `result: false` refusal as final instead of
  retrying, and read the car's state rather than resend when a command is not
  confirmed. Unlocking and disarming Sentry Mode are restated as access changes.
- Each car accepts the key once, by pairing it from the Tesla app;
  `tesla_get_fleet_status` reports which VINs are paired, which is what a `403`
  on a command usually means.
- Not included: setting charge or preconditioning schedules, media, trunks,
  windows, seat heaters, HomeLink, software updates, PIN to Drive, valet mode,
  speed limits, parental controls, energy products, Fleet Telemetry, and
  charging invoice downloads.
