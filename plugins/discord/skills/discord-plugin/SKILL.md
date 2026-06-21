---
name: discord-plugin
description: Use for ANY Discord request — servers (guilds), channels, messages, or members, or a discord.com link — to list, read, or summarize. Hits the Discord REST API directly via the Fermix Discord plugin. Read-only.
---

# Discord

Use the `discord_*` tools for anything on Discord — servers (guilds), channels, messages, or members. Do NOT use the browser for Discord; these tools call the REST API directly with the bot token and return clean data.

This plugin is **read-only** and acts as a **bot**: it only sees servers the bot has been invited to.

## Pick the tool

- Servers: `discord_list_guilds` — find a server and its `id` first · `discord_get_guild` for one server's details and member counts.
- Channels: `discord_list_channels` — list a server's channels (and their `id`s).
- Messages: `discord_channel_messages` — read recent messages by channel `id`.
- Members: `discord_list_members` — list a server's members.

Discord ids are **snowflakes** (long numeric strings). Resolve names to ids by listing guilds, then channels, then reading.

## Preconditions — read this before promising results

The bot must already be **in the server** with `VIEW_CHANNEL` + `READ_MESSAGE_HISTORY`, or reads return nothing or a permission error. Beyond that, two **privileged gateway intents** gate whole categories of data, and when they are off the API does not error — it silently returns empty fields. Name this to the user rather than guessing:

- **Empty message content.** Without the **`MESSAGE_CONTENT`** privileged intent enabled on the bot, `discord_channel_messages` returns messages whose `content` is an empty string (author, timestamp, and attachments still come through). If content is blank across the board, that's the cause — tell the user to enable `MESSAGE_CONTENT` in the Developer Portal, not that the channel is empty.
- **Member list unavailable.** `discord_list_members` needs the **`GUILD_MEMBERS`** privileged intent. Without it the call fails; surface that as the reason.

Apps in 100+ servers must verify the app before these intents can be toggled — flag that if the user can't enable them.

## No message search

Discord has **no bot REST endpoint for searching messages** — there is deliberately no `discord_search` tool. To find something, read the relevant channel's recent history with `discord_channel_messages` and reason over it (page back with `before` if needed). Don't claim a search capability.

## Notes

- `discord_channel_messages` pages via the `before` id window (newest-first), bounded at 5 pages × `limit` ≤ 100. Say when you stopped early.
- No posting, editing, reactions, joining/leaving servers, role or moderation actions. Don't claim those.
- If the `discord_*` tools aren't available, the plugin isn't connected — tell the user to add a Discord bot token on the Fermix setup page. On an auth error, say to re-paste the token; don't fall back to the browser.
