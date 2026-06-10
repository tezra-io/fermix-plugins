---
name: obsidian-plugin
description: Search, read, create, and append to markdown notes in the user's local Obsidian vault through the Fermix Obsidian plugin, respecting vault path conventions.
---

# Obsidian

Use this skill when the Obsidian plugin is enabled and a vault path is configured. The vault is read as plain files — the Obsidian app does not need to be running.

## Tools

Read:
- `obsidian_search_notes` (read-only) — case-insensitive search over note filenames and contents. Args: `query`, optional `limit` (default 10, max 50). Returns matching paths with a snippet line for content matches.
- `obsidian_read_note` (read-only) — one note's full markdown. Args: `path`.
- `obsidian_list_folder` (read-only) — notes and folders under a vault path. Args: optional `path` (omit for the vault root). Folders end with `/`.

Write:
- `obsidian_create_note` — new note. Args: `path`, `content`. Refuses to overwrite an existing note; missing parent folders are created.
- `obsidian_append_note` — add to an existing note. Args: `path`, `content`. Refuses if the note does not exist.

## Vault path conventions

- Paths are always vault-relative: `folder/note.md`, never a leading slash, never absolute, never `..`.
- Notes are markdown — every note path ends in `.md`.
- Dot-entries (`.obsidian`, `.trash`) are the app's own state; the tools skip them and you should never touch them.

## Working the vault

- **Search before read:** find the right note with `obsidian_search_notes` or `obsidian_list_folder` first; only `obsidian_read_note` what you matched. Don't guess paths.
- **Append vs. create:** adding to an existing note (a daily log, a running list) is `obsidian_append_note`; a genuinely new note is `obsidian_create_note`. The tools refuse the wrong one — a "note already exists" error means append, "note not found" means create.
- **The vault is the user's second brain — never restructure it unasked.** Don't rename, move, reorganize, or rewrite existing notes on your own initiative; add new notes or append to existing ones where the user's layout already puts them. There is deliberately no delete or overwrite tool.

## Failure modes

- "OBSIDIAN_VAULT_PATH is not set" or a `:needs_config` plugin status — the vault path hasn't been configured: `fermix plugins config set obsidian OBSIDIAN_VAULT_PATH <path>` or the setup page.
- "path escapes the vault" — the path was absolute or contained `..`; use a vault-relative path.
- An empty search result usually means the term isn't in the vault — try a shorter or different query before concluding the note doesn't exist.
