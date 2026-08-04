# Changelog

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
