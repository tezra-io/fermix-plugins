# Eden plugin

Search, read, capture, and connect knowledge in an [Eden](https://eden.so)
workspace from Fermix. First `remote_mcp`-rail plugin: nothing but
`plugin.json`, a logo, and a skill — no code, no vendored dependencies, no
local process. Fermix connects straight from the BEAM to Eden's hosted MCP
server ([`https://mcp.eden.so/mcp`](https://eden.so/features/mcp/)) over
Streamable HTTP.

**Unofficial.** This is a community integration built by the Fermix project
against Eden's public MCP documentation. It is not endorsed by, affiliated
with, or supported by Eden. "Eden" is used only to identify what the plugin
interoperates with.

## Eden is a hosted service — read this before connecting

- Eden is a **US-incorporated hosted cloud service**, not a local vault.
  Selected Fermix queries and content are sent to it over the network. There
  is no offline mode and no self-hosted option.
- **Eden MCP requires a paid Eden plan** (currently Personal Plus and above).
  See [pricing](https://eden.so/pricing/).
- **Some operations are metered against your EdenAI credit balance.** Observed
  against a live account: `eden_find_workspace_items` (semantic search),
  `eden_read_board`, and `eden_search_highlights` all refuse with
  `out_of_credits` once the balance is exhausted, while literal search
  (`eden_search_workspace_items`), listing, and note reads keep working. See
  [how credits work](https://eden.so/help/account/how-credits-work/). The plugin
  skill tells the model to prefer the free tools and to disclose the cost before
  using a metered one, but it cannot refund a balance — an agent left to browse
  boards will spend credits.
- **Eden AI features may route relevant content to third-party model
  providers** under Eden's own terms. Read the
  [privacy policy](https://eden.so/privacy/) and
  [terms](https://eden.so/terms/) before connecting.
- Eden results flow back into your configured Fermix model provider and local
  conversation history; with Fermix's global content-capture setting enabled
  they can also reach local traces and your configured Opik exporter.
- **You are responsible for having the rights** to save or process the
  third-party links, posts, documents, and media you ask Fermix to put into
  Eden.

Using a read-only token does not make Eden local, offline, or zero-retention.

## Auth — an Eden personal access token

1. In Eden, open **Settings → Integrations → API access** and create a
   personal access token. Eden's
   [CLI guide](https://eden.so/help/eden-mcp/installing-with-cli/) and
   [automation-tool guide](https://eden.so/help/eden-mcp/connecting-n8n/)
   cover the flow; the general client guide is
   [Connecting AI assistants](https://eden.so/help/eden-mcp/connecting-ai-assistants/).
   Eden says this Integrations surface is **still rolling out gradually**, so
   PAT creation may not appear on every account yet.
2. Choose the token's permission deliberately. **Pick read-only if you only
   want retrieval** — a read/write token authorizes far more upstream than
   Fermix ever exposes (Eden's full surface includes publishing, scheduling,
   media generation, and social tooling that this plugin excludes entirely).
3. Paste the token into the Fermix setup page's Eden card. It is stored in
   your OS keychain; the config file holds only a sentinel. The token is shown
   once by Eden and can be revoked there immediately.

Browser OAuth is not used. Eden's OAuth server relies on Dynamic Client
Registration, which Fermix's static OAuth provider registry does not support
yet.

## Workspace and access profile

Setup requires choosing **exactly one workspace**. Fermix lists your
workspaces once during setup, stores the ID you pick as ordinary plugin
config, and injects it into every subsequent call. The agent has no tool to
list or switch workspaces — a token that can reach ten workspaces still only
reaches the one you selected. Changing it is an explicit reconnect.

| Profile | Default | Token | Agent-visible tools |
|---|---|---|---:|
| `retrieval` | Yes | Read-only is enough | 12 read-only tools |
| `capture` | No — explicit opt-in | Requires read/write | 19 (12 read + 7 additive write) |

The profile is local, signed policy. `retrieval` never exposes a write tool
even when the token itself is broader, and there is no automatic downgrade
from `capture` after a permission failure.

## Tools

Retrieval (`retrieval` and `capture`):

| Tool | What it does |
|---|---|
| `eden_list_workspace_items` | Browse saved items, bounded pagination |
| `eden_search_workspace_items` | Literal title/URL/text search |
| `eden_find_workspace_items` | Semantic search — **credit-metered** |
| `eden_read_board` | A board and the items placed on it — **credit-metered** |
| `eden_read_media_card` | Metadata for saved media (generates nothing) |
| `eden_read_social_post` | One social post, by Eden id or by `url` (an uncached `url` costs vendor quota) |
| `eden_get_note_markdown` | A note as Markdown |
| `eden_get_connections` | An item's connections — `include: ["existing"]` or `["suggested"]`, both when omitted |
| `eden_search_highlights` | Highlights — pass `q` to search, omit `q` to list — **credit-metered** |

Capture (`capture` only, all additive):

| Tool | What it does |
|---|---|
| `eden_create_note` | Create a workspace item — `presentation: "document"` (default) or `"card"` |
| `eden_append_to_note` | Append Markdown to an existing note |
| `eden_create_board` | Create a board |
| `eden_save_links_to_board` | Save operator-supplied public links to a board |
| `eden_save_posts_to_board` | Save operator-supplied social posts to a board |
| `eden_connect_items` | Relate two known items |

There is no update-in-place, delete, trash, or rename tool. Note replacement,
board rename/trash, scheduling, publishing, global social search, creator
analysis, media generation, voice/brief/identity management, and Eden skill
import/export are all excluded — Eden advertising a tool never widens Fermix,
because the signed manifest, not the remote server, decides what registers.

The `eden-plugin` skill teaches the agent Eden's item/board/connection model,
literal-before-semantic search, search-before-read, sticky-vs-note capture,
and the structured-error recovery paths.

## No bulk extraction

This integration is interactive and user-directed. It does not crawl, mirror,
bulk-export, or continuously synchronize an Eden workspace, and there is no
sync engine, poller, or webhook consumer between Eden, Obsidian, and Fermix
memory. Fermix enforces hard ceilings per turn and per call; the skill refuses
crawl/dump/mirror requests outright. Eden's terms prohibit bulk extraction.

## Disconnecting

Three different actions, deliberately distinct:

- **Disable Eden** — stops the connection and hides the tools; the local token
  is kept for a later re-enable.
- **Forget local credential** — stops the connection and deletes the token
  from your OS keychain. **This is not upstream revocation.** A copy of the
  token taken elsewhere still works.
- **Revoke upstream** — do this in **Eden → Settings → Integrations**. That is
  the only thing that actually invalidates the token.

## Eden and Obsidian

They are complementary, not competing: Obsidian is the local, file-owned,
offline-capable vault; Eden is the hosted workspace with semantic retrieval,
highlights, boards, and connections. Fermix does not prefer or auto-route
between them — your request decides, and content is copied across only when
you explicitly ask.

## Eden documentation

[The library](https://eden.so/help/library/the-library/) ·
[Creating notes and cards](https://eden.so/help/library/creating-items-in-the-library/) ·
[Searching your library](https://eden.so/help/library/searching-your-library/) ·
[Connecting items](https://eden.so/help/library/connecting-items/) ·
[Boards, spaces, and sections](https://eden.so/help/boards/creating-your-first-board/) ·
[Eden MCP](https://eden.so/features/mcp/)
