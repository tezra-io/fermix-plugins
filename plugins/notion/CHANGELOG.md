# Changelog

## 1.0.1

- Stronger skill trigger and a tighter, token-efficient skill body so the agent
  uses these tools instead of the browser. Tool descriptions unchanged.

## 1.0.0

- Initial release: declarative http-rail plugin, zero code.
- 9 tools: `notion_search`, `notion_get_page`, `notion_get_block_children`,
  `notion_create_page`, `notion_update_page`, `notion_append_blocks`,
  `notion_get_data_source`, `notion_query_data_source`, `notion_get_me`.
- Cursor pagination (`start_cursor`/`next_cursor`) on search, data-source
  query, and block children; compact field extraction on the single-object
  reads.
- OAuth2 via the operator's own Notion public connection (no scopes — access
  is granted through Notion's page picker at login).
- `notion-plugin` skill: search-then-read flow, page vs. data-source model,
  block/property JSON cookbook.
