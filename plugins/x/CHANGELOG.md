# Changelog

## 1.0.2

- The agent no longer refuses what the X API can't do. The skill used to forbid
  the browser for anything on X and end every failed call with "reconnect"; it
  now starts with the `x_*` tools and moves to x.com in the browser for actions
  a pay-per-use X app is refused (liking, following, quoting, blocking,
  reporting, replying to a post that didn't summon the user), for what the
  plugin has no tool for (DMs, bookmarks, mutes, media), and for a call X
  refuses for a reason a retry or a reconnect won't change. A 401 or a missing
  scope is still a reconnect.
- Tool descriptions no longer tell the agent to avoid the browser for X.
- Cost notes follow X's April 2026 pricing: the user's own posts and mentions
  read at ~$0.001 each.

## 1.0.1

- Tighter, more token-efficient tool descriptions and skill trigger: dropped the
  redundant "/Twitter" from every tool description (the `x_*` namespace already
  disambiguates), trimmed the always-in-context skill frontmatter, and merged the
  redundant write-discipline section into the tool list. No behavior change; cost
  guardrails and the id workflow are unchanged.

## 1.0.0

- Initial release: declarative http-rail plugin, zero code.
- 11 tools: `x_whoami`, `x_get_user`, `x_search_posts`, `x_get_post`,
  `x_user_posts`, `x_mentions`, `x_home_timeline`, `x_create_post`,
  `x_delete_post`, `x_like_post`, `x_repost`.
- OAuth2 (PKCE) via the operator's own X developer app (confidential client,
  HTTP Basic token exchange); scopes `tweet.read`, `users.read`, `tweet.write`,
  `like.write`, `offline.access`.
- Cost-aware by design: reads default to 10 results and never auto-paginate
  (each returned post is billed on X's pay-per-use credits); the skill teaches
  the id workflow, cost guardrails, and the reconnect-on-401 flow.
- Not included: media upload, DMs, bookmarks, follows, quote posts
  (Enterprise-gated).
