# fermix-plugins

Optional, separately-installed plugins for [Fermix](https://github.com/tezra-io/fermix). Each lives in
`apps/` and attaches to Fermix at runtime; none is required for Fermix to run.

| App | What it does |
|-----|--------------|
| [`fermix_opik`](apps/fermix_opik) | Exports Fermix's telemetry to [Opik](https://www.comet.com/docs/opik/) (Comet's open-source LLM observability/eval tool) for trace inspection, cost tracking, and evaluation. |

---

## fermix_opik

`fermix_opik` turns Fermix's telemetry into Opik **traces** so you can see what a
run actually did — every LLM call, every tool call, every subagent it delegated
to, every scheduled job — with token usage and auto-computed cost, instead of
grepping JSONL logs.

It is a telemetry **reporter**: it runs in the same BEAM as Fermix, subscribes to
Fermix's `:telemetry` events, reassembles them, and POSTs to Opik's native REST
batch API. Disabled by default — zero overhead until you turn it on.

### The trace model

One Opik **trace** is one top-level run:

- a **main agent turn** (one user message → reply), or
- one **scheduled job run**.

Inside a trace, every *run* becomes a `general` **wrapper span**, and work nests
under it by Fermix's `session_id` / `parent_session`:

```
Trace  "agent:main"  (thread_id = chat_id)
├─ span general  "agent:main"
│  ├─ span llm   "llm:codex:gpt-5-codex"   usage{prompt,completion,total} → cost
│  ├─ span tool  "shell"
│  └─ span general "subagent:coder"        ← delegated subagent, same trace
│     ├─ span llm  "llm:gpt-5"
│     └─ span tool "file_write"
└─ ...
```

Cost is **not** computed by the plugin: Opik derives USD from `provider` +
`model` + `usage`, so the `llm` spans just carry those fields.

### Requirements (Fermix side)

This plugin relies on correlation fields Fermix emits on its telemetry
(`session_id` on `provider.call` / `tool.exec`, the `[:fermix, :job, :run_*]`
lifecycle events, and turn `input`/`output`). Those ship in Fermix itself — no
patch needed beyond having a Fermix build that includes them.

Prompt/response/tool bodies are captured when **content capture** is on.
Enabling the exporter turns it **on by default** — if you're observing, you
want to see everything — so `FERMIX_OPIK_ENABLED=1` is the only switch you need.
`FERMIX_TRACE_CONTENT` is the explicit override:

```sh
FERMIX_OPIK_ENABLED=1                        # Opik on + content on  (the common case)
FERMIX_OPIK_ENABLED=1 FERMIX_TRACE_CONTENT=0 # Opik on, bodies off   (privacy)
FERMIX_TRACE_CONTENT=1                        # content in local JSONL, no Opik
```

### Install (wire into Fermix)

Add the app as a dependency of the Fermix umbrella (it must be in the same
release to receive in-VM telemetry), then enable it:

```elixir
# fermix/apps/fermix_core/mix.exs (or wherever the release deps live)
{:fermix_opik, path: "../../../fermix-plugins/apps/fermix_opik"}
```

```sh
# enable + point at your local Opik (defaults shown)
export FERMIX_OPIK_ENABLED=1
export FERMIX_OPIK_BASE_URL=http://localhost:5173/api   # docker-compose Opik
export FERMIX_OPIK_PROJECT=fermix
# Opik Cloud only:
# export FERMIX_OPIK_API_KEY=...   FERMIX_OPIK_WORKSPACE=...
```

Start Fermix; new turns appear in the Opik project as they complete.

### Replay historical traces

Already have Fermix JSONL traces on disk? Replay them into Opik (great for
evaluating past runs, or backfilling after an e2e session) — same reassembly
logic, no live daemon needed:

```sh
cd fermix-plugins
mix opik.replay --dir ~/.fermix-dev/traces --project fermix
mix opik.replay --dir ~/.fermix/traces --dry-run     # report counts, don't post
```

### Configuration

`config :fermix_opik` (env vars override at runtime):

| Key | Env | Default | Meaning |
|-----|-----|---------|---------|
| `enabled` | `FERMIX_OPIK_ENABLED` | `false` | Attach the reporter |
| `base_url` | `FERMIX_OPIK_BASE_URL` | `http://localhost:5173/api` | Opik REST root (incl. the nginx `/api` hop) |
| `project_name` | `FERMIX_OPIK_PROJECT` | `fermix` | Opik project |
| `api_key` | `FERMIX_OPIK_API_KEY` | `nil` | Opik Cloud only (local needs none) |
| `workspace` | `FERMIX_OPIK_WORKSPACE` | `nil` | Opik Cloud only |
| `trace_ttl_ms` | — | `120_000` | Force-flush a run whose completion was missed |
| `max_queue` | — | `500` | Drop (and log) sends past this backlog — never block the agent |

### Design notes

- **Never degrades the agent.** The telemetry handler only stamps a time and
  casts to the `Aggregator`; assembly and HTTP happen off the hot path in the
  `Aggregator`/`Sender`. If Opik is slow or down, sends are dropped past
  `max_queue` and logged — observability can't apply backpressure to Fermix.
- **Bounded.** A periodic sweep force-flushes runs whose root never signalled
  completion, so no trace leaks.
- **Distinct traces per run (not idempotent across runs).** Ids are minted
  fresh (random UUIDv7) each run, so re-running `opik.replay` over the *same*
  files creates duplicate traces — Opik upserts by id, but the ids differ each
  run. This is intentional: two *different* runs (e.g. before vs after a change)
  are distinct runs and stay as separate, comparable traces, which is what you
  want for eval. (A stable per-run key is also genuinely tricky — `session_id`
  isn't unique across daemon restarts.) To compare runs, use Opik **threads**
  (turns in a chat group by `thread_id = channel:chat_id`) and **experiments**;
  to avoid accidental dupes, just don't re-push the same files.

### Internals

| Module | Role |
|--------|------|
| `FermixOpik.Reporter` | Attaches to Fermix telemetry; casts events to the aggregator |
| `FermixOpik.Aggregation` | Pure reducer: session/parent tree → closed traces+spans |
| `FermixOpik.Aggregator` | GenServer wrapping `Aggregation` for live events + sweep |
| `FermixOpik.Mapper` | Pure field builders matching Opik's REST write schema |
| `FermixOpik.Sender` | Serializes deliveries off the hot path |
| `FermixOpik.Client` | Req-based POST to `/v1/private/{traces,spans}/batch` |
| `FermixOpik.TraceFile` | Rebuilds events from Fermix JSONL (for replay) |
| `Mix.Tasks.Opik.Replay` | `mix opik.replay` |

### Opik REST reference (for maintainers)

Native batch ingestion, no auth for local docker-compose Opik:

```
POST {base_url}/v1/private/traces/batch   {"traces": [TraceWrite, ...]}   → 204
POST {base_url}/v1/private/spans/batch    {"spans":  [SpanWrite,  ...]}   → 204
```

- Span `type` ∈ `general | tool | llm | guardrail`. Only `llm` spans get cost.
- `usage` keys are integers `prompt_tokens` / `completion_tokens` /
  `total_tokens`; `provider` is a short token (`openai`, `anthropic`, …) and
  `model` is the bare id — together they drive auto-cost.
- Conversation grouping is `thread_id` on the **trace**.
- Timestamps are ISO-8601 UTC (ms). Ids are UUIDv7 so id-order ≈ time-order.

### Develop

```sh
mix deps.get
mix check   # format --check-formatted + credo --strict + test
```
