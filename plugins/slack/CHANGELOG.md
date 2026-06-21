# Changelog

## 1.0.0

Initial release.

- 5 declarative http-rail tools against the Slack Web API (`slack.com/api`): channels (`slack_list_channels`), messages (`slack_channel_history`), threads (`slack_channel_replies`), workspace (`slack_team_info`), members (`slack_list_members`).
- OAuth2 browser login with read-only bot scopes against an operator-registered Slack app.
- Cursor pagination on the list/history tools (bounded at 5 pages).
- `slack-plugin` skill: channel-id-vs-name guidance, thread reads, rate-limit honesty, the deferred user-token search caveat.
