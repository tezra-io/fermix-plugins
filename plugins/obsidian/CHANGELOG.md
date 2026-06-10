# Changelog

## 1.0.0

- Initial release: first `mcp`-rail plugin — a first-party MCP stdio server
  (MIT, Node ≥ 20, single dependency `@modelcontextprotocol/sdk`, vendored
  under `src/node_modules/`).
- 5 tools: `obsidian_search_notes`, `obsidian_read_note`,
  `obsidian_create_note`, `obsidian_append_note`, `obsidian_list_folder`.
- Vault path via the plugin-config mechanism (`OBSIDIAN_VAULT_PATH`,
  required) — no auth.
- Path safety: every path resolves inside the vault root; absolute paths and
  `..` are rejected. Create refuses overwrite; append refuses missing notes;
  no delete/move/rename tools.
- `obsidian-plugin` skill: vault path conventions, search-before-read,
  append-vs-create, never restructure the vault unasked.
