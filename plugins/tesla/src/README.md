# fermix-tesla

The signing half of the Fermix Tesla plugin: an MCP server, spoken over stdio,
whose tools send **signed vehicle commands** to the operator's car using
Tesla's official [`vehicle-command`](https://github.com/teslamotors/vehicle-command)
SDK.

The read-only Tesla tools (`tesla_list_vehicles`, `tesla_get_vehicle_data`,
`tesla_wake_vehicle` and the rest) are plain HTTP-rail tools declared in
`plugins/tesla/plugin.json`. They are not served by this binary. Commands that
change the car's state cannot go over that rail, because Tesla requires them to
be end-to-end signed with a key the car has paired.

## How Fermix spawns it

The daemon runs the binary as a local plugin process, talks JSON-RPC 2.0 over
stdin and stdout (MCP, protocol version `2025-06-18`), and registers every tool
it advertises under the plugin's prefix. Tool names here are therefore
**unprefixed**: `start_charging` reaches the model as `tesla_start_charging`.

stdout is the wire. Every diagnostic this binary writes goes to stderr, and
every line is redacted of token and key material first.

## Environment

| Variable | Required | Meaning |
| --- | --- | --- |
| `FERMIX_PLUGIN_TOKEN_FILE` | yes | Path to the daemon-owned JSON token file. |
| `SIGNING_KEY_PATH` | yes | Path to the application's prime256v1 private key, PEM. |
| `FERMIX_TESLA_USER_AGENT` | no | Replaces the default `fermix-tesla/<version>` user agent. |

The token file looks like this:

```json
{
  "access_token": "<Tesla Fleet API OAuth access token>",
  "expires_at": "2026-09-13T13:00:00Z",
  "region": "eu",
  "auth_profile": "tesla:primary",
  "generation": 4
}
```

Both files are read **on every command**, never cached: the daemon rewrites the
token file when it refreshes the sign-in, and a key that was sound at startup
is not the guarantee worth having. `region` is informational — the regional
Fleet API host comes from the token's own `aud` claim, which is what the SDK's
`account.New` reads.

A call is refused before anything reaches the network when the token file is
missing, unreadable, malformed, or expires within 30 seconds; and when the
signing key is unset, missing, not a regular file, readable by group or others
(`mode & 0o077`), or not a P-256 key. Each refusal is one sentence naming the
one correction.

## Tools

Twenty-three commands, each taking a 17-character `vin`:

| Tool | Extra arguments | Vehicle subsystem |
| --- | --- | --- |
| `start_charging` | — | infotainment |
| `stop_charging` | — | infotainment |
| `set_charge_limit` | `percent` 50–100 | infotainment |
| `set_charging_amps` | `amps` 1–48 | infotainment |
| `open_charge_port` | — | infotainment |
| `close_charge_port` | — | infotainment |
| `start_climate` | — | infotainment |
| `stop_climate` | — | infotainment |
| `set_cabin_temperature` | `driver_celsius` 15–28, `passenger_celsius` optional | infotainment |
| `set_preconditioning_max` | `enabled` | infotainment |
| `lock_doors` | — | VCSEC |
| `unlock_doors` | — | VCSEC |
| `set_sentry_mode` | `enabled` | infotainment |
| `flash_lights` | — | infotainment |
| `honk_horn` | — | infotainment |
| `set_seat_heater` | `seat`, `level` 0–3 | infotainment |
| `set_seat_cooler` | `seat` (front only), `level` 0–3 | infotainment |
| `set_auto_seat_climate` | `seat` (front only), `enabled` | infotainment |
| `set_steering_wheel_heater` | `enabled` | infotainment |
| `actuate_trunk` | `which` front or rear | VCSEC |
| `vent_windows` | — | infotainment |
| `close_windows` | — | infotainment |
| `set_vehicle_name` | `name`, 1–32 characters | infotainment |

Each call opens a session on **only** the subsystem its command terminates on,
so a lock never wakes infotainment. The trunk is a closure action, which the
SDK sends to the security controller rather than to infotainment; the windows
are not.

`seat` is one of `front_left`, `front_right`, `rear_left`, `rear_center`,
`rear_right`, `rear_left_back`, `rear_right_back`, `third_row_left`,
`third_row_right` — the nine positions `SetSeatHeater` can address. Seat
cooling and automatic seat climate take **only the front two**: the SDK's
`AutoSeatAndClimate` drops any other position from the request and its
protobuf has no rear value at all, so advertising a rear seat there would be
advertising a command that does nothing. `level` is the SDK's own scale: 0
off, 1 low, 2 medium, 3 high.

Seat heating, seat cooling and steering wheel heating need the car's climate
control to be on. When it is not, the car authenticates the command and
declines it, which comes back as `result: false` with the car's own reason —
the same as any other refusal. `actuate_trunk` with `front` opens the frunk
and cannot close it; with `rear` it moves the rear trunk, which opens a closed
one and closes an open one on cars with a powered rear trunk.

`navigate_to` is deliberately absent. The SDK has no typed navigation method,
and its command proxy maps `navigation_request` to `ErrCommandUseRESTAPI`
because the endpoint needs server-side processing that end-to-end
authentication cannot survive. Navigation ships as a plain HTTP-rail tool.

This binary never wakes a car. If the car is asleep the command is refused with
a sentence pointing at `tesla_wake_vehicle`.

## Results

A command that reached the car returns a normal result whose single text
content is JSON:

```json
{"command":"start_charging","vin":"5YJ…","result":true,"reason":"","dispatched_at":"2026-09-13T12:34:56Z"}
```

`result` is `false` with the car's own words in `reason` when the car
authenticated the command and declined it — already charging, charge port
already open, and so on. That is an answer, not a failure.

Anything that means the command did **not** reach the car comes back as an
error result with one plain sentence. A command that went out and was never
confirmed is reported as exactly that, never as a failure, because a retry
would send it twice.

Each command is dispatched exactly once; this package adds no retry of its own.

## Build

```sh
./build.sh                  # every target
./build.sh macos-aarch64    # one target
```

Targets are `macos-aarch64`, `macos-x86_64`, `linux-x86_64`, `linux-aarch64`.
Binaries land in `plugins/tesla/bin/<target>/fermix-tesla`, built with
`CGO_ENABLED=0 -trimpath -ldflags="-s -w"`. That directory is gitignored;
binaries are published through a release.

## Gates

```sh
gofmt -l .
go vet ./...
go test -race ./...
go build ./...
```

The tests never call Tesla: the SDK vehicle sits behind a small interface that
the tests replace with a fake.

## Versioning

`internal/tesla.Version` must be kept in step with the `version` field of
`plugins/tesla/plugin.json`. The two are read by different tools, so
`TestVersionMatchesManifest` compares them: `go test` fails, and the release
lane with it, when a bump touched only one.
