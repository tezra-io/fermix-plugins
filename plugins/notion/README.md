# Notion plugin

Search, read, create, and update Notion pages and data sources from Fermix.
Pure declarative `http`-rail plugin: nothing but `plugin.json`, a logo, and a
skill — no code, no runtime.

## Auth — your own Notion public connection

The plugin signs in with OAuth against an integration **you** register (one
time):

1. In the [Notion Developer portal](https://www.notion.so/profile/integrations),
   create an integration and make it a **public connection** (OAuth). No Notion
   review is needed to use it yourself — review applies only to optional
   Marketplace listing; "Selected workspaces only" distribution is fine for
   personal use.
2. Register the redirect URI **exactly** as
   `http://127.0.0.1:1458/auth/callback` — Notion matches redirect URIs
   exactly, port included, so the port must be `1458` (Fermix binds it fixed,
   no fallback).
3. Paste the integration's client id and client secret into the Fermix setup
   page (the secret is stored in your OS keychain). Token exchange uses HTTP
   Basic auth with `client_id:client_secret`, handled by Fermix.

On Connect, Notion's grant screen shows a **page picker**: the connection sees
only the pages and data sources you select there. Re-run Connect any time to
grant more pages. Notion has no OAuth scopes — the page picker is the access
model.

## Tools

| Tool | What it does |
|---|---|
| `notion_search` | Search pages and data sources by title (paginated) |
| `notion_get_page` | One page's metadata and properties |
| `notion_get_block_children` | A page's content blocks (paginated) |
| `notion_create_page` | Create a page under a page or in a data source |
| `notion_update_page` | Update properties on an existing page |
| `notion_append_blocks` | Append content blocks to a page |
| `notion_get_data_source` | A data source's schema |
| `notion_query_data_source` | Query a data source's pages (paginated) |
| `notion_get_me` | The connection's bot user (login probe) |

All requests pin `Notion-Version: 2026-03-11` and address **data sources**,
not bare database ids (the 2025-09 API split). The `notion-plugin` skill
teaches the agent the search-then-read flow and the block/property JSON
shapes.
