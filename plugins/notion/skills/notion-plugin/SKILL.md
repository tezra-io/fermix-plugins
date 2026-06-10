---
name: notion-plugin
description: Search, read, create, and update Notion pages and data sources (databases) through the Fermix Notion plugin, building block and property JSON correctly.
---

# Notion

Use this skill when the Notion plugin is enabled and connected. Search first, read second, write only on clear intent — and build block/property JSON from the cookbook below, never from guesswork.

## Tools

Read:
- `notion_search` (read-only) — find pages and data sources by title. Args: `query`, optional `filter` (`{"property": "object", "value": "page"}` or `"data_source"`). Returns `id`, `object`, `url`, `parent`, `properties`/`title` per match.
- `notion_get_page` (read-only) — one page's metadata and properties. Args: `page_id`. Properties only — page content is blocks; use `notion_get_block_children`.
- `notion_get_block_children` (read-only) — a page's (or block's) content blocks. Args: `block_id` (a page id works), optional `page_size`.
- `notion_get_data_source` (read-only) — a data source's schema: property names, types, select options. Args: `data_source_id`. Read this before filtering or writing properties.
- `notion_query_data_source` (read-only) — the pages (rows) in a data source. Args: `data_source_id`, optional `filter`, `sorts`.
- `notion_get_me` (read-only) — the connection's bot user; a cheap "is the login alive?" probe.

Write:
- `notion_create_page` — new page. Args: `parent`, `properties`, optional `children` (content blocks).
- `notion_update_page` — change properties on an existing page. Args: `page_id`, `properties` (only the ones to change).
- `notion_append_blocks` — add content blocks to a page. Args: `block_id` (page id), `children`.

## Pages vs. data sources

Notion split databases into **data sources** (2025-09): a database is a container; its rows live in a *data source*. Always address data sources, never bare database ids:

1. `notion_search` with filter `{"property": "object", "value": "data_source"}` to find one.
2. `notion_query_data_source` with its `id` to list rows (each row is a page).
3. To add a row: `notion_create_page` with parent `{"data_source_id": "..."}` and properties matching the schema from `notion_get_data_source`.

A plain page's content is blocks (`notion_get_block_children`); a data-source row's content is its `properties` plus optional blocks.

## Cookbook — block and property JSON

Blocks (for `children` in `notion_create_page` / `notion_append_blocks`):

```json
{"object": "block", "type": "paragraph",
 "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Hello"}}]}}

{"object": "block", "type": "heading_2",
 "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Section"}}]}}

{"object": "block", "type": "to_do",
 "to_do": {"rich_text": [{"type": "text", "text": {"content": "Task"}}], "checked": false}}
```

`heading_1`/`heading_3`, `bulleted_list_item`, `numbered_list_item`, `quote`, and `callout` all follow the `paragraph` shape (content under the type key, text in `rich_text`).

Properties (for `properties` in `notion_create_page` / `notion_update_page`):

```json
{"Name":   {"title": [{"type": "text", "text": {"content": "Page title"}}]},
 "Notes":  {"rich_text": [{"type": "text", "text": {"content": "Some text"}}]},
 "Status": {"select": {"name": "In progress"}},
 "Due":    {"date": {"start": "2026-06-15"}}}
```

Property keys must match the data source's schema exactly (case-sensitive) — read `notion_get_data_source` first. A page created under a plain page (`{"page_id": "..."}` parent) takes only the title property, keyed `"title"`.

## Workflow

1. Search before reading: resolve names to ids with `notion_search`; never invent ids.
2. Read before writing: `notion_get_data_source` before property writes; `notion_get_page` before updates.
3. Confirm destructive-feeling changes (overwriting properties, large appends) before writing; report the page `url` after a successful write.
4. Paginated reads (`search`, `query`, `block_children`) return `{"items": [...], "truncated": bool}` — when `truncated` is true, say the list is partial.

## Access model

The OAuth grant shows a **page picker** — the connection sees only the pages and data sources the user selected at login. An empty `notion_search` result usually means no pages were granted, not an empty workspace: tell the user to reconnect the plugin and pick pages (re-running the login adds grants).

## Limitations

Can search, read pages/blocks/data sources, create and update pages, and append blocks. It does not delete or archive pages, edit or remove existing blocks, manage comments or users, or create databases. Do not claim those actions.

## Examples

- "What's on my Ideas page?" → `notion_search` "Ideas" → `notion_get_block_children` with the page id, summarize.
- "Add 'Ship v2' to my Tasks database." → search for the Tasks data source → `notion_get_data_source` for the schema → `notion_create_page` with `{"data_source_id": ...}` parent and matching properties.
- "Append meeting notes to today's journal." → search, confirm the target page, then `notion_append_blocks` with paragraph blocks.
