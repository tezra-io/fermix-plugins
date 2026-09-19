# Tesla plugin

Read your Tesla from Fermix: charge and range, climate, location, alerts,
service and software, nearby chargers, charging history, warranty — and, if you
allow it, control it: start and stop charging, set the charge limit, run
climate, warm the seats, lock and unlock, open the trunk, vent the windows, arm
Sentry Mode, send a destination, wake it up.

The reads are declarative `http`-rail tools Fermix calls itself. The commands
go through `fermix-tesla`, a small helper built from `src/` in this repo and
shipped inside the plugin artifact, because modern vehicles require Tesla's
signed command protocol — a command has to be signed with your application's
private key and delivered end to end to the car, which a URL template cannot do.

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
   The private key never leaves your machine. Keep it: it is what signs every
   vehicle command, and [Vehicle commands](#vehicle-commands) below is where you
   point Fermix at it.

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
| `vehicle_charging_cmds` | Charging history, and the charging commands (start, stop, limit, amps, charge port) |
| `vehicle_cmds` | The mobile-access check, `tesla_wake_vehicle`, and every other vehicle command |

## Wake and cost

Waking and commands are off until you turn them on, behind one switch — see
[Vehicle commands](#vehicle-commands). Leave it off and `tesla_wake_vehicle`
and every command tool do not exist, so the agent can offer to wake or move
nothing. Sleep is how a parked Tesla keeps its charge, and every wake is billed.

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

## Vehicle commands

Commands are off until you turn them on. Turn on the plugin's **Allow vehicle
commands** switch and the command tools — and `tesla_wake_vehicle` — are
advertised to the agent; leave it off and none of them exist. One switch covers
all of them, waking included. In `config.toml`:

```toml
[fermix_core.plugins.tesla]
ALLOW_COMMANDS = "true"
SIGNING_KEY_PATH = "/path/to/tesla-private-key.pem"
```

### The signing key

`SIGNING_KEY_PATH` is the private half of the key pair you generated during
onboarding — the same `tesla-private-key.pem` whose public half you published at
`/.well-known/appspecific/com.tesla.3p.public-key.pem`. Every command is signed
with it inside the car's own protocol, so without it there are no commands.

Keep the file readable by you and nobody else (`chmod 600`). Fermix passes the
*path* to the helper; the key is never copied into `config.toml`, never sent to
Tesla, and never leaves the machine.

### Pair the key with each car, once

Publishing the key is not enough: each car has to accept it. On a phone signed
in to the Tesla account, with the Tesla app installed, open

```
https://tesla.com/_ak/fermix.ai
```

(replace `fermix.ai` with the domain you registered) and follow the prompt to
add the virtual key to that car. The account must already have granted
`vehicle_cmds`, and you repeat it for every car.

`tesla_get_fleet_status` reports the result: it returns `key_paired_vins` and
`unpaired_vins`, plus each car's firmware and whether it requires the signed
command protocol. A car in `unpaired_vins` will refuse every command with a
`403` no matter how the switch is set — that is the first thing to check when a
command fails and a read succeeds.

### What you can command

| Tool | What it does |
|---|---|
| `tesla_start_charging` | Start charging (the car must be plugged in) |
| `tesla_stop_charging` | Stop charging |
| `tesla_set_charge_limit` | Set the charge limit, 50-100% |
| `tesla_set_charging_amps` | Set the charging current, 1-48 A |
| `tesla_open_charge_port` | Open the charge port door, or unlock the cable |
| `tesla_close_charge_port` | Close the charge port door |
| `tesla_start_climate` | Turn climate on and precondition the cabin |
| `tesla_stop_climate` | Turn climate off |
| `tesla_set_cabin_temperature` | Set driver (and optionally passenger) temperature, 15-28 °C |
| `tesla_set_preconditioning_max` | Turn max defrost on or off |
| `tesla_set_seat_heater` | Set one seat's heater, 0-3 (climate must be on) |
| `tesla_set_seat_cooler` | Set a front seat's cooler, 0-3 (climate must be on) |
| `tesla_set_auto_seat_climate` | Turn a front seat's automatic climate on or off |
| `tesla_set_steering_wheel_heater` | Turn the steering wheel heater on or off (climate must be on) |
| `tesla_lock_doors` | Lock the doors |
| `tesla_unlock_doors` | Unlock the doors |
| `tesla_actuate_trunk` | Open the front trunk, or open or close the rear |
| `tesla_vent_windows` | Vent the windows |
| `tesla_close_windows` | Close the windows |
| `tesla_set_sentry_mode` | Arm or disarm Sentry Mode |
| `tesla_flash_lights` | Flash the headlights once |
| `tesla_honk_horn` | Honk the horn once |
| `tesla_set_vehicle_name` | Rename the car as it shows in the app |
| `tesla_navigate_to` | Send a destination by coordinates |
| `tesla_send_navigation` | Send a full street address (a bare place name does not resolve) |
| `tesla_navigate_waypoints` | Send a route of Google Maps place IDs |
| `tesla_wake_vehicle` | Wake a sleeping car |

Every one takes the VIN. The skill makes the agent name the action and the car
and wait for a yes before each command, treat a refusal from the car as final
rather than retrying, and read the car's state rather than resend when a command
is not confirmed. Unlocking and disarming Sentry Mode are called out as access
changes and confirmed on their own.

### Billing

Tesla meters commands the same way it meters reads, at its own published
command rate, and enforces a per-car limit (30 commands a minute at the time of
writing). Check the current figures on
[developer.tesla.com](https://developer.tesla.com). A command costs money every
time it is sent, including one sent twice because the first looked unconfirmed
— which is why the skill reads the state instead of resending.

### How it runs

The three navigation tools (`tesla_navigate_to`, `tesla_send_navigation` and
`tesla_navigate_waypoints`) are plain Fleet API calls, because Tesla's own SDK
routes those over REST rather than the signed protocol. Every other command goes
through `fermix-tesla`, a helper Fermix runs on this machine as a local MCP
server and stops again the moment the switch goes off. It is built from `src/`
in this repo, cross-compiled by the release workflow and shipped **inside** the
signed plugin artifact — there is nothing to install separately and nothing is
downloaded at run time. Fermix hands it the account's access token and the path
from `SIGNING_KEY_PATH`; it holds no credentials of its own.

## What you can reuse from another install, and what you cannot

The plugin is open source and every operator brings their own Tesla developer
application, so it helps to know which parts of a working setup carry over:

- **The redirect page carries over.** `https://fermix.ai/api/integrations/tesla/callback`
  is a static page that forwards the sign-in to the daemon on your own
  computer and keeps nothing, so any Fermix operator can register it on their
  own application. (Or host the same page yourself.)
- **Nothing key-related carries over.** Tesla binds the public key to the
  domain your application registered as its allowed origin, and binds the
  partner registration to your client ID. The pairing link is
  `https://tesla.com/_ak/<your-domain>`, and a car accepts only commands
  signed with the private half of the key it paired. So you need your own
  domain (a static host that can serve one file under `/.well-known/` is
  enough), your own key pair, your own registration in each region, and your
  own pairing on each car. Never use, publish or accept anyone else's private
  key: whoever holds it can command every car that paired it.

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
| `tesla_wake_vehicle` | Wake a sleeping car (billed) |

Plus the command tools, all of them behind the `ALLOW_COMMANDS` switch:
see [Vehicle commands](#vehicle-commands).

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
| `tesla_wake_vehicle` | `POST /vehicles/{vin}/wake_up` | `vehicle_device_data`, `vehicle_cmds` | Wakes the car, at the wake rate; gated on `ALLOW_COMMANDS` |
| `tesla_navigate_to` | `POST /vehicles/{vin}/command/navigation_gps_request` | `vehicle_cmds` | Command rate; gated on `ALLOW_COMMANDS` |
| `tesla_send_navigation` | `POST /vehicles/{vin}/command/navigation_request` | `vehicle_cmds` | Command rate; gated on `ALLOW_COMMANDS` |
| `tesla_navigate_waypoints` | `POST /vehicles/{vin}/command/navigation_waypoints_request` | `vehicle_cmds` | Command rate; gated on `ALLOW_COMMANDS` |

The other command tools have no row here: they are not REST calls. They are
signed end to end and delivered to the car by `fermix-tesla`, so there is no
URL to quote.

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

Not included: setting charge or preconditioning schedules (they can be read,
not written), the sunroof, the steering-wheel heater's level and its automatic
mode (on and off are covered), upcoming calendar entries, media and volume,
HomeLink, software updates, PIN to Drive, valet mode, speed limits and parental
controls, energy products (Powerwall, solar, Wall Connector), Fleet Telemetry
streaming and its history, and charging invoice downloads. The `tesla-plugin`
skill teaches the agent the VIN workflow, which section answers which
question, the asleep-car rules, the rule that every command is confirmed on
its own, and the cost guardrails.
