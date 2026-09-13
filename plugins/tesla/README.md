# Tesla plugin

Read your Tesla from Fermix: charge and range, climate, location, alerts,
service and software, nearby chargers, charging history, warranty — and,
if you allow it, wake a sleeping car. Pure declarative `http`-rail plugin:
nothing but `plugin.json`, a logo, and a skill — no code, no runtime.

Vehicle commands (start charging, set the temperature, lock the doors) are
**not** included. Modern vehicles require Tesla's signed command protocol,
which needs a local signing helper; that is a later piece of work, not a
missing manifest entry.

## Auth — your own Tesla developer app

The plugin signs in with OAuth 2.0 against an application **you** register.
Tesla's onboarding is longer than most: an app alone is not enough, you also
publish a public key on a domain you control and register that domain once per
region.

1. Create an account on the
   [Tesla developer portal](https://developer.tesla.com) and request an
   application. Tesla asks for your business details and the scopes you want;
   tick **Vehicle Information**, **Vehicle Location**, **Vehicle Charging
   Management**, and **Vehicle Commands**. Approval is not instant.

2. Set the application's URLs:
   - **Allowed Origin URL**: the domain you own, e.g. `https://fermix.ai`.
   - **Allowed Redirect URI**: exactly
     `https://fermix.ai/api/integrations/tesla/callback`.

   Tesla accepts only public `https` redirects: a loopback URL such as
   `http://127.0.0.1:1461/auth/callback` is rejected outright. That
   Fermix-hosted page is static: it forwards the finished sign-in to the daemon
   on this computer at `http://localhost:1461/auth/callback` and keeps nothing.
   If you would rather not involve it, host the same static page on your own
   domain and set `redirect_uri` under `[fermix_core.oauth.tesla]`.

3. Generate a key pair and publish the public half on your domain:

   ```sh
   openssl ecparam -name prime256v1 -genkey -noout -out tesla-private-key.pem
   openssl ec -in tesla-private-key.pem -pubout -out com.tesla.3p.public-key.pem
   ```

   Serve that second file at exactly
   `https://<your-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem`.
   The private key never leaves your machine and Fermix never reads it — this
   release signs nothing; the file is what a later command helper would use.

4. Register the domain once per region you use. Get a short-lived partner
   token (this is not your owner login):

   ```sh
   curl --request POST 'https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token' \
     --header 'Content-Type: application/x-www-form-urlencoded' \
     --data-urlencode 'grant_type=client_credentials' \
     --data-urlencode "client_id=$TESLA_CLIENT_ID" \
     --data-urlencode "client_secret=$TESLA_CLIENT_SECRET" \
     --data-urlencode 'scope=openid vehicle_device_data vehicle_location vehicle_charging_cmds vehicle_cmds' \
     --data-urlencode 'audience=https://fleet-api.prd.na.vn.cloud.tesla.com'
   ```

   Then register, and read the key back to prove Tesla fetched it:

   ```sh
   curl --request POST 'https://fleet-api.prd.na.vn.cloud.tesla.com/api/1/partner_accounts' \
     --header "Authorization: Bearer $PARTNER_TOKEN" \
     --header 'Content-Type: application/json' \
     --data '{"domain": "<your-domain>"}'

   curl 'https://fleet-api.prd.na.vn.cloud.tesla.com/api/1/partner_accounts/public_key?domain=<your-domain>' \
     --header "Authorization: Bearer $PARTNER_TOKEN"
   ```

   Use the `eu` base URL for both the `audience` and the two calls if you
   register Europe. Skipping this step is what a `412` means later.

5. Put the application's **Client ID** and **Client Secret** into Fermix's
   sign-in client for Tesla (the secret goes to your OS keychain) and choose
   the **region your Tesla account belongs to**. There is no default. Tesla
   assigns the region by the account's home country, not by where you live:
   North America and Asia-Pacific, or Europe, Middle East and Africa. The
   region picks both the token `audience` and the Fleet API host every tool
   calls. After each sign-in Fermix asks Tesla which region the account is in
   and flags the row if the two disagree, so a wrong choice never surfaces as
   a `421` from the first question. In `config.toml` the same choice is
   `region = "na"` or `"eu"` under `[fermix_core.oauth.tesla]`.

6. Connect on the Fermix setup page. Tesla's consent screen lists the scopes
   below. Refresh tokens last about three months and are rotated on use;
   Fermix persists the rotated token, and if a refresh ever fails, reconnect.

### Scopes requested

| Scope | What it grants |
|---|---|
| `openid` | The sign-in itself |
| `offline_access` | Refresh, so you don't re-authorize every few hours |
| `vehicle_device_data` | Vehicle list, status, live data sections, alerts, service, release notes, options, warranty, nearby chargers |
| `vehicle_location` | Live GPS position (`tesla_get_vehicle_location` only) |
| `vehicle_charging_cmds` | Charging history — Tesla bundles history with charging control in one scope; this plugin only reads |
| `vehicle_cmds` | The mobile-access check and `tesla_wake_vehicle` |

## Wake and cost

Waking is off until you turn it on. Set the plugin's `ALLOW_WAKE` setting to
exactly `true` and `tesla_wake_vehicle` is advertised to the agent; leave it
unset and the tool does not exist, so the agent can offer to wake nothing.
Sleep is how a parked Tesla keeps its charge, and every wake is billed.

Tesla meters Fleet API usage: per data request, per command, and per wake, with
a monthly discount (currently $10) that covers a small personal app, and
published per-vehicle limits of **60 data requests, 30 commands, and 3 wakes a
minute**. At the time of writing Tesla lists $0.002 per data request, $0.001
per command, and $0.02 per wake. Treat those as dated figures and check the
current ones on [developer.tesla.com](https://developer.tesla.com).

What that means in practice: every call is metered, and a wake costs about
ten times a read. Cloud reads (`vehicle_status`, `fleet_status`, service,
release notes, options, warranty) and charging history answer while the car
sleeps; live reads (`vehicle_data`, location, nearby chargers) need it awake,
which is where a wake starts to look tempting. The skill tells the agent to
fetch one section per question, never to poll, and never to wake a car just to
answer a read.

## Regions

| Region | Fleet API host |
|---|---|
| `na` | `https://fleet-api.prd.na.vn.cloud.tesla.com` — North America and Asia-Pacific except China |
| `eu` | `https://fleet-api.prd.eu.vn.cloud.tesla.com` — Europe, Middle East, Africa |

Every tool carries both hosts; Fermix picks one from your verified region, so
no model argument and no upstream redirect can change where a request goes.
China runs on a separate host with its own application and onboarding and is
not covered by an `na`/`eu` grant — it is excluded from this release.

## Tools

| Tool | What it does |
|---|---|
| `tesla_list_vehicles` | Cars on the account, with VIN and cloud state (call once, reuse the VIN) |
| `tesla_get_vehicle_status` | Online / asleep / offline for one car, without waking it |
| `tesla_get_vehicle_data` | One live section: charge, climate, vehicle state, config, closures, display units, schedules |
| `tesla_get_vehicle_location` | Where the car is right now |
| `tesla_get_fleet_status` | Firmware, command protocol, virtual key pairing, telemetry version |
| `tesla_get_mobile_access` | Whether the car's Allow Mobile Access setting is on |
| `tesla_get_vehicle_alerts` | Recent alerts the car raised |
| `tesla_get_service_status` | Service state, estimated completion, visit number |
| `tesla_get_release_notes` | Release notes for the installed or staged software |
| `tesla_get_nearby_charging_sites` | Superchargers and destination chargers near the car |
| `tesla_list_charging_history` | Tesla-billed charging sessions with fees |
| `tesla_get_vehicle_options` | Trim, paint, wheels and packages as option codes |
| `tesla_get_warranty` | Active, upcoming and expired warranty terms |
| `tesla_wake_vehicle` | Wake a sleeping car (needs `ALLOW_WAKE`; billed) |

## API reference

Paths are relative to the regional base, under `/api/1`. Tesla meters every
call; "cloud read" below means it answers while the car sleeps, not that it is
free.

| Tool | Method and path | Scope | Notes |
|---|---|---|---|
| `tesla_list_vehicles` | `GET /vehicles` | `vehicle_device_data` | Cloud read |
| `tesla_get_vehicle_status` | `GET /vehicles/{vin}` | `vehicle_device_data` | Cloud read; never wakes |
| `tesla_get_vehicle_data` | `GET /vehicles/{vin}/vehicle_data?endpoints={section}` | `vehicle_device_data` | Live read; needs the car online (`408` when asleep) |
| `tesla_get_vehicle_location` | `GET /vehicles/{vin}/vehicle_data?endpoints=location_data` | `vehicle_device_data`, `vehicle_location` | Live read; needs the car online; visible in the car |
| `tesla_get_fleet_status` | `POST /vehicles/fleet_status` | `vehicle_device_data` | Cloud read; a POST that only reads |
| `tesla_get_mobile_access` | `GET /vehicles/{vin}/mobile_enabled` | `vehicle_cmds` | Cloud read |
| `tesla_get_vehicle_alerts` | `GET /vehicles/{vin}/recent_alerts` | `vehicle_device_data` | Cloud read |
| `tesla_get_service_status` | `GET /vehicles/{vin}/service_data` | `vehicle_device_data` | Cloud read |
| `tesla_get_release_notes` | `GET /vehicles/{vin}/release_notes?staged={staged}` | `vehicle_device_data` | Cloud read |
| `tesla_get_nearby_charging_sites` | `GET /vehicles/{vin}/nearby_charging_sites?count={count}&radius={radius}` | `vehicle_device_data` | Live read; needs the car online |
| `tesla_list_charging_history` | `GET /dx/charging/history?vin={vin}&startTime=…&endTime=…&pageNo=…&pageSize=…` | `vehicle_charging_cmds` | Account read; one page per call |
| `tesla_get_vehicle_options` | `GET /dx/vehicles/options?vin={vin}` | `vehicle_device_data` | Account read |
| `tesla_get_warranty` | `GET /dx/warranty/details?vin={vin}` | `vehicle_device_data` | Account read |
| `tesla_wake_vehicle` | `POST /vehicles/{vin}/wake_up` | `vehicle_device_data`, `vehicle_cmds` | Wakes the car, at the wake rate; gated on `ALLOW_WAKE` |

## Privacy

- `tesla_get_vehicle_location` is a separate tool on a separate scope for a
  reason: it returns where the car is, and the car shows a location-sharing
  icon on its screen while the request is served. Nobody gets a silent trace.
- `tesla_get_nearby_charging_sites` answers from the car's current position, so
  its results reveal roughly where the car is even though no coordinates are
  returned.
- `tesla_list_charging_history` contains site names, times and fees — a travel
  record. The skill reads it only when asked and never pages through it to be
  thorough.
- Everything else is vehicle condition, not movement.

Not included (yet): signed vehicle commands of every kind (charging start/stop,
charge limit and amps, climate and preconditioning, locks, horn, lights,
windows, trunks, sentry, navigation), energy products (Powerwall, solar, Wall
Connector), Fleet Telemetry streaming and its history, and charging invoice
downloads. The `tesla-plugin` skill teaches the agent the VIN workflow, which
section answers which question, the asleep-car rules, and the cost guardrails.
