import Config

# FermixOpik exports Fermix's telemetry to a local (or remote) Opik instance.
#
# Disabled by default — set `enabled: true` (or FERMIX_OPIK_ENABLED=1) to attach.
# `base_url` is the Opik REST root reached through the frontend nginx proxy; for
# a default local docker-compose Opik that is http://localhost:5173/api.
config :fermix_opik,
  enabled: false,
  base_url: "http://localhost:5173/api",
  project_name: "fermix",
  # Optional Opik Cloud auth (omit for local). When set, sent as headers.
  api_key: nil,
  workspace: nil,
  # Flush a finished trace's spans no later than this after its last event,
  # even if the closing event was missed.
  trace_ttl_ms: 120_000,
  # Drop (and log) sends once this many traces are queued, so a slow/unreachable
  # Opik can never apply backpressure to the agent.
  max_queue: 500

import_config "#{config_env()}.exs"
