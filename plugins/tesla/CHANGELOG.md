# Changelog

## 1.0.0

- Initial release: declarative http-rail plugin, zero code.
- 14 tools: `tesla_list_vehicles`, `tesla_get_vehicle_status`,
  `tesla_get_vehicle_data`, `tesla_get_vehicle_location`,
  `tesla_get_fleet_status`, `tesla_get_mobile_access`,
  `tesla_get_vehicle_alerts`, `tesla_get_service_status`,
  `tesla_get_release_notes`, `tesla_get_nearby_charging_sites`,
  `tesla_list_charging_history`, `tesla_get_vehicle_options`,
  `tesla_get_warranty`, `tesla_wake_vehicle`.
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
- Waking is off until the operator sets `ALLOW_WAKE` to `true`; until then
  `tesla_wake_vehicle` is not advertised at all.
- Not included: signed vehicle commands (charging, climate, locks and the rest
  need Tesla's signed command protocol), energy products, Fleet Telemetry, and
  charging invoice downloads.
