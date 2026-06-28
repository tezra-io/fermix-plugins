# Changelog

## 1.0.0

Initial release.

- 5 declarative http-rail tools against the Discord REST API (`discord.com/api/v10`): servers (`discord_list_guilds`, `discord_get_guild`), channels (`discord_list_channels`), messages (`discord_channel_messages`), members (`discord_list_members`).
- Bot-token auth (`Authorization: Bot <token>`) stored in the OS keychain, with the required `User-Agent` on every request.
- Id-window pagination on `discord_channel_messages` (bounded at 5 pages).
- `discord-plugin` skill: the `MESSAGE_CONTENT` / `GUILD_MEMBERS` privileged-intent preconditions, "no message search — read history and reason", snowflake-id guidance.
