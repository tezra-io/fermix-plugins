---
name: notion-plugin
description: Use for ANY Notion request — pages, databases/data sources, or a notion.so link — to search, read, create, or update. Hits the Notion API directly via the Fermix Notion plugin; build block and property JSON from the cookbook below.
---

# Notion

Use the `notion_*` tools for anything in Notion — pages, databases (data sources), or a `notion.so` link. Do NOT use the browser or web search for Notion; these tools call the API directly and need no login or scraping. Search first, read second, write only on clear intent — and build block/property JSON from the cookbook, never from guesswork.

## Pick the tool

Read:
- `notion_search` — find pages and data sources by title (optional `filter` `{"property":"object","value":"page"}` or `"data_source"`). Always resolve names to ids here; never invent ids.
- `notion_get_page` — one page's metadata and properties (NOT its content; content is blocks).
- `notion_get_block_children` — a page's content blocks (a page id works as `block_id`).
- `notion_get_data_source` — a data source's schema (property names, types, options). Read before filtering or writing properties.
- `notion_query_data_source` — the pages (rows) in a data source, with optional `filter`/`sorts`.
- `notion_get_me` — the connection's bot user; a cheap "is the login alive?" probe.

Write (confirm overwrites / large appends):
- `notion_create_page` — new page (`parent`, `properties`, optional `children` blocks).
- `notion_update_page` — change properties on an existing page (only the ones to change).
- `notion_append_blocks` — add content blocks to a page (`block_id` = page id, `children`).

## Pages vs. data sources (databases)

Notion split databases into **data sources** (2025-09): a database is a container; its rows live in a *data source*. Always address data sources, never bare database ids:

1. `notion_search` with filter `{"property":"object","value":"data_source"}` to find one.
2. `notion_query_data_source` with its `id` to list rows (each row is a page).
3. To add a row: `notion_create_page` with parent `{"data_source_id":"..."}` and properties matching `notion_get_data_source`.

A plain page's content is blocks; a data-source row's content is its `properties` plus optional blocks.

## Cookbook — block and property JSON

Blocks (for `children`):

```json
{"object": "block", "type": "paragraph",
 "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Hello"}}]}}

{"object": "block", "type": "heading_2",
 "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Section"}}]}}

{"object": "block", "type": "to_do",
 "to_do": {"rich_text": [{"type": "text", "text": {"content": "Task"}}], "checked": false}}
```

`heading_1`/`heading_3`, `bulleted_list_item`, `numbered_list_item`, `quote`, and `callout` follow the `paragraph` shape (content under the type key, text in `rich_text`).

Properties (for `properties`):

```json
{"Name":   {"title": [{"type": "text", "text": {"content": "Page title"}}]},
 "Notes":  {"rich_text": [{"type": "text", "text": {"content": "Some text"}}]},
 "Status": {"select": {"name": "In progress"}},
 "Due":    {"date": {"start": "2026-06-15"}}}
```

Property keys must match the schema exactly (case-sensitive) — read `notion_get_data_source` first. A page under a plain page (`{"page_id":"..."}` parent) takes only the title property, keyed `"title"`.

## Notes

- Read before writing: `notion_get_data_source` before property writes; `notion_get_page` before updates. Report the page `url` after a successful write.
- Paginated reads (`search`, `query`, `block_children`) return `{"items":[...],"truncated":bool}` — say the list is partial when `truncated`.
- **Access model:** the OAuth grant shows a **page picker** — the connection sees only the pages and data sources the user selected at login. An empty `notion_search` usually means no pages were granted, not an empty workspace; tell the user to reconnect and pick pages.
- Cannot delete/archive pages, edit/remove blocks, manage comments/users, or create databases. Don't claim those.
- If the `notion_*` tools aren't available, the plugin isn't connected — tell the user to connect Notion on the Fermix setup page. On auth errors, say to reconnect; don't loop or fall back to the browser.
