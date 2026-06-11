# Changelog

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
