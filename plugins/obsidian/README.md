# Obsidian plugin

Search, read, create, and append to markdown notes in your local Obsidian
vault from Fermix. First `mcp`-rail plugin: a small first-party MCP server
(Node, stdio) ships inside the plugin with its dependencies vendored under
`src/node_modules/` — nothing is downloaded at install or spawn time.

The vault is read directly from the filesystem, so the **Obsidian app does
not need to be running**. Requires Node ≥ 20 on the host (Fermix probes for
it and never installs it).

## Configuration

No login — the one required setting is the vault path:

```sh
fermix plugins config set obsidian OBSIDIAN_VAULT_PATH /path/to/your/vault
```

or enter it in the form on the setup page's Obsidian card. Until it is set,
the plugin holds at `needs_config` and registers no tools.

## Consent

Enabling this plugin runs a local process with direct access to the
configured vault folder. It can read every note and create or append to
notes; it has no delete, overwrite, or rename capability, and no network
access.

## Tools

| Tool | What it does |
|---|---|
| `obsidian_search_notes` | Case-insensitive search over note filenames and contents |
| `obsidian_read_note` | Read one note's markdown |
| `obsidian_create_note` | Create a new note (refuses to overwrite) |
| `obsidian_append_note` | Append to an existing note (refuses if missing) |
| `obsidian_list_folder` | List notes/folders under a vault path |

Paths are always vault-relative (`folder/note.md`); absolute paths and `..`
are rejected. The `obsidian-plugin` skill teaches the agent the
search-before-read flow and the append-vs-create choice.

No logo ships with this plugin: Obsidian's brand guidelines reserve the
logo for licensed use ("If you want to use Obsidian assets for commercial
purposes, please contact us"), so the card renders without one.
