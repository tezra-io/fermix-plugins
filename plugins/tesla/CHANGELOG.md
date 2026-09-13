# Changelog

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
