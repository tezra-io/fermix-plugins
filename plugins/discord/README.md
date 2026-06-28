# Discord plugin

Declarative (http-rail) Fermix plugin for Discord: read servers (guilds), channels, messages, and members via the Discord REST API (`discord.com/api/v10`). Pure `plugin.json` — no code, no runtime.

## Auth

API key (a **Discord bot token**), stored in the OS keychain:

1. Create an application at <https://discord.com/developers/applications>, add a Bot, and copy its token.
2. Invite the bot to your server with the `VIEW_CHANNEL` and `READ_MESSAGE_HISTORY` permissions.
3. Paste the token into Fermix (setup page or config). The token is sent as `Authorization: Bot <token>`.

To read message *content* and member lists you must also enable two **privileged gateway intents** on the bot — see the skill for details.

## Tools

| Tool | What it does |
|---|---|
| `discord_list_guilds` | List servers the bot is in |
| `discord_get_guild` | Get one server, with counts |
| `discord_list_channels` | List channels in a server |
| `discord_channel_messages` | Read recent messages in a channel |
| `discord_list_members` | List members of a server |

All read-only. Discord has no bot REST message search, so there is no `discord_search` tool.
