# Slack plugin

Declarative (http-rail) Fermix plugin for Slack: read channels, messages, threads, and members via the Slack Web API (`slack.com/api`). Pure `plugin.json` — no code, no runtime.

## Auth

OAuth2 browser login against an **operator-registered Slack app**:

1. Create an app at <https://api.slack.com/apps>.
2. Add the bot scopes below under OAuth & Permissions, and set the redirect URL to the loopback callback Fermix prints during connect.
3. Paste the client ID + secret into Fermix (setup page or config); the secret is stored in the OS keychain.

Bot scopes requested: `team:read`, `channels:read`, `groups:read`, `im:read`, `mpim:read`, `channels:history`, `groups:history`, `im:history`, `mpim:history`, `users:read`. All read-only — the plugin never posts to Slack.

## Tools

| Tool | What it does |
|---|---|
| `slack_list_channels` | List channels (public, private, DMs) |
| `slack_channel_history` | Read recent messages in a channel |
| `slack_channel_replies` | Read a thread's replies |
| `slack_team_info` | Workspace name, domain, id |
| `slack_list_members` | List workspace members |

Message search (`slack_search_messages`) is **not yet available** — it needs a Slack user token, which lands in a later wave.
