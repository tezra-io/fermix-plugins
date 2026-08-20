# Changelog

## 1.1.0

- Repairs the plugin against a breaking change in Eden's hosted API. Eden's
  live surface grew from 20 tools to 59, and in the process **withdrew or
  stubbed five tools this manifest signed**. Because the signed allowlist is
  all-or-none, that did not degrade the plugin — it **refused it entirely**:
  every install failed its contract check with
  `upstream_contract_mismatch/missing_tool` and registered zero Eden tools, on
  both profiles. This release restores the capability; it does not add any.
- Capability is **remapped, not dropped**. Three tools were withdrawn outright
  and two now answer with an empty schema and a "moved" notice:
  - `eden_get_item_connections` and `eden_get_suggested_connections` →
    `eden_get_connections`, with `include: ["existing"]` / `["suggested"]`.
    Omitting `include` returns both. One signed entry now grants what two
    granted separately, so a profile can no longer allow explicit links while
    withholding semantic suggestions.
  - `eden_list_highlights` → `eden_search_highlights` with `q` **omitted**.
    An empty `q` is refused by the schema rather than treated as a list.
  - `eden_read_card` → `eden_read_social_post`, which now also accepts a
    `url`.
  - `eden_create_sticky_note` → `eden_create_note` with
    `presentation: "card"`.
- 15 agent tools behind the same two profiles: `retrieval` (default, 9
  read-only) and `capture` (explicit opt-in, adds **6** additive writes — one
  fewer than 1.0.0 because sticky notes are now a presentation of
  `eden_create_note`, not a separate tool). `eden_list_workspaces` remains
  signed as setup-only and is unchanged.
- Three descriptors were re-signed because Eden reshaped them:
  `eden_read_social_post` (adds `url`; no longer requires `contentId` +
  `platform`), `eden_search_highlights` (adds `offset` and `orderBy`; `q` now
  optional), and `eden_create_note` (adds `presentation` and `color`). The
  remaining twelve hash exactly as before.
- `eden_read_social_post` can now be given a `url` the model chose rather than
  an id from a prior Eden result, and an uncached `url` makes Eden fetch the
  page live against the operator's vendor quota. The manifest cannot guard a
  scalar URL — its guard vocabulary is array-shaped — so this is bounded by
  instruction: the skill now tells the agent to pass only a URL the operator
  supplied or that came from an Eden result, and to disclose the cost first.
- Excluded on purpose, now against a 59-tool upstream: scheduling,
  publishing, analytics, custom AI, tables, global social search, creator
  analysis, auto-DM automation, note replacement, board rename/trash, media
  generation, voice/brief/identity management, and Eden skill import/export.
  The signed allowlist remains the enforcement boundary — a new tool upstream
  never widens Fermix.
- `min_core_version` and `plugin_api` are unchanged: this repair uses only
  manifest grammar that already existed, so raising the floor would strip the
  fix from the operators who need it.

## 1.0.0

- Initial release: first `remote_mcp`-rail plugin — a signed manifest, a logo,
  and a skill, with no code, no vendored dependencies, and no local process.
  Fermix connects directly to Eden's hosted MCP server
  (`https://mcp.eden.so/mcp`, Streamable HTTP, MCP `2025-06-18`).
- 19 agent tools behind two local access profiles. `retrieval` (default, 12
  read-only): `eden_list_workspace_items`, `eden_search_workspace_items`,
  `eden_find_workspace_items`, `eden_read_board`, `eden_read_card`,
  `eden_read_media_card`, `eden_read_social_post`, `eden_get_note_markdown`,
  `eden_get_item_connections`, `eden_get_suggested_connections`,
  `eden_search_highlights`, `eden_list_highlights`. `capture` (explicit
  opt-in, adds 7 additive writes): `eden_create_note`, `eden_append_to_note`,
  `eden_create_sticky_note`, `eden_create_board`, `eden_save_links_to_board`,
  `eden_save_posts_to_board`, `eden_connect_items`.
- `eden_list_workspaces` is signed as setup-only: setup lists workspaces once,
  the operator selects exactly one, and its ID is injected into every later
  call. The agent can never enumerate or switch workspaces.
- Auth by Eden personal access token (`eden_pat_` prefix, keychain-stored,
  sent as `Authorization: Bearer`). Read-only is sufficient for `retrieval`;
  `capture` requires a read/write token, which authorizes more upstream than
  this plugin exposes.
- Excluded on purpose: note replacement, board rename/trash, scheduling,
  publishing, global social search, creator analysis, media generation,
  voice/brief/identity management, and Eden skill import/export. The signed
  allowlist is the enforcement boundary — a new tool upstream never widens
  Fermix.
- Bounded by construction: per-turn call and pagination budgets, capped
  returned collections, capped save batches, public-HTTP(S)-only URL guards on
  the save tools. No crawling, mirroring, bulk export, or sync.
- `eden-plugin` skill: the canonical-item/board/connection model (boards are
  curated views, not duplicate storage), literal-before-semantic search with
  cost disclosure before any credit-metered call, search-before-read and
  read-before-append, sticky-vs-note capture, retrieved content treated as
  untrusted data, structured-status recovery, no auto-retry of an ambiguous
  write, and no browser/shell/REST/Obsidian fallback.
- Unofficial integration; not endorsed by or affiliated with Eden. Eden MCP
  requires a paid Eden plan. Three tools are metered against the account's
  EdenAI credit balance — `eden_find_workspace_items`, `eden_read_board`, and
  `eden_search_highlights` — and refuse with `out_of_credits` once it is spent;
  literal search, listing, and note reads keep working.
