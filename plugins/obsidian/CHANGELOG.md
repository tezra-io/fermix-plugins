# Changelog

## 1.0.5

- A link inside the vault no longer reaches a file outside it. Paths were
  checked only as written, so a symlink planted in the vault let
  `obsidian_read_note` read any file the user can (an SSH key, say) and
  `obsidian_append_note` add to one (a shell profile), and creating a note at
  a dangling link made its target outside the vault. Every path now has to
  resolve, links followed, inside the vault's real folder, or the call fails
  with "path escapes the vault"; create refuses anything already at the path,
  a dangling link included.
- Notes in a folder linked into the vault from elsewhere on disk can no
  longer be read, listed or added to through the plugin (search already
  skipped them). Links between notes inside the vault keep working.

## 1.0.4

- A vault path written from your home folder (`~/Documents/Vault`) now works.
  Nothing expanded the `~`, so the server looked for a folder literally named
  `~` and stopped with "OBSIDIAN_VAULT_PATH does not exist".

## 1.0.3

- Clearer tool descriptions and a stronger skill trigger so the agent uses the
  vault tools instead of the browser or a raw filesystem read.

## 1.0.2

- Replace the logo with a clean 128px transparent PNG of the Obsidian mark.

## 1.0.1

- Add the Obsidian logo (`assets/logo.png`) so the catalog card is branded.

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
