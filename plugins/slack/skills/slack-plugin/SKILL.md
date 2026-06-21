---
name: slack-plugin
description: Use for ANY Slack request — channels, messages, threads, members, or a slack.com link — to list, read, or summarize workspace activity. Hits the Slack Web API directly via the Fermix Slack plugin. Read-only.
---

# Slack

Use the `slack_*` tools for anything on Slack — channels, messages, threads, members, or a `slack.com` link. Do NOT use the browser or web search for Slack; these tools call the Web API directly and return clean data.

This plugin is **read-only**: it never posts messages, joins channels, or changes anything.

## Pick the tool

- Channels: `slack_list_channels` — find a channel and its `id` before reading.
- Messages in a channel: `slack_channel_history` — takes the channel `id`, not the name.
- Thread replies: `slack_channel_replies` — takes the channel `id` plus the parent message `ts`.
- Workspace: `slack_team_info` — name, domain, id.
- People: `slack_list_members` — list users in the workspace.

## Ids vs names

Slack's read APIs work on **ids**, not human names. `#general` is a label; the API needs `C0123ABCD`. Resolve names to ids first: call `slack_list_channels` for channels and `slack_list_members` for users, match the name, then read with the id. A bare `ts` like `1718900000.001200` is a message timestamp and doubles as its id for `slack_channel_replies`.

## Reading threads

`slack_channel_history` returns top-level messages; ones with a `thread_ts` and a `reply_count > 0` have a thread. To read it, call `slack_channel_replies` with that message's `ts`.

## Not yet available: search

There is no `slack_search_messages` tool yet. Slack's `search.messages` needs a Slack **user token**, which this connection does not store. Don't claim you can search Slack — instead list the relevant channel and read its history, or ask the user which channel to look in.

## Notes

- Pagination is cursor-based and auto-pages up to 5 pages; results may be partial on large workspaces — keep `limit` modest (50–100) and say when you stopped early.
- Slack apps distributed outside the Marketplace are throttled hard on `conversations.history`/`conversations.replies` (~1 request/min). An auth/rate error surfaces as a tool error; don't hammer it — back off and tell the user.
- No posting, reactions, file uploads, channel joins, admin actions, or DMs you aren't already in. Don't claim those; point the user to Slack.
- If the `slack_*` tools aren't available, the plugin isn't connected — tell the user to connect Slack on the Fermix setup page. If a call returns an auth error, say to reconnect; don't fall back to the browser.
