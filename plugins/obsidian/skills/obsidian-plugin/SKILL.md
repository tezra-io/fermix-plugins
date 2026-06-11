---
name: obsidian-plugin
description: Use for ANYTHING in the user's Obsidian vault — search, read, create, append, or list notes and folders. Reads the vault files directly via the Fermix Obsidian plugin; the Obsidian app need not be running.
---

# Obsidian

Use the `obsidian_*` tools for anything in the user's Obsidian vault. Do NOT use the browser, web search, or a raw filesystem read for vault notes — these tools read the vault files directly and the Obsidian app need not be running.

## Pick the tool

Read:
- `obsidian_search_notes` — case-insensitive search over note names and contents; returns paths with a snippet per content match.
- `obsidian_read_note` — one note's full markdown by path.
- `obsidian_list_folder` — notes and folders under a path (omit `path` for the vault root); folders end with `/`.

Write:
- `obsidian_create_note` — a genuinely new note; refuses to overwrite, creates missing parent folders.
- `obsidian_append_note` — add to an existing note (a daily log, a running list); refuses if the note is missing.

**Search before read:** find the note with `obsidian_search_notes` or `obsidian_list_folder` first; only read what you matched — don't guess paths. The create/append pair refuses the wrong one: "note already exists" means append, "note not found" means create.

## Vault path conventions

- Paths are vault-relative: `folder/note.md` — never a leading slash, absolute path, or `..`.
- Every note path ends in `.md`.
- Dot-entries (`.obsidian`, `.trash`) are app state; the tools skip them and you never touch them.

## The vault is the user's second brain — never restructure it unasked

Don't rename, move, reorganize, or rewrite existing notes on your own initiative; add new notes or append where the user's layout already puts them. There is deliberately no delete or overwrite tool.

## Notes

- An empty search usually means the term isn't in the vault — try a shorter/different query before concluding the note is absent.
- "path escapes the vault" — the path was absolute or had `..`; use a vault-relative path.
- If the `obsidian_*` tools aren't available or a call returns "OBSIDIAN_VAULT_PATH is not set" / `:needs_config`, the vault path isn't configured — tell the user to set it on the Fermix setup page (or `fermix plugins config set obsidian OBSIDIAN_VAULT_PATH <path>`). Don't fall back to the browser.
