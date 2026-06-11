---
name: x-plugin
description: Use for ANY X (Twitter) request — post, reply, delete, like, repost, search, or read timelines/mentions/users. Hits the X API directly via the Fermix plugin — never the browser or web_search for X.
---

# X (Twitter)

Use the `x_*` tools for anything on X (Twitter). They call the X API directly — no login, no scraping. Do NOT use the browser or `web_search` for X content.

## ID workflow (read this first)

X's API addresses people by **numeric user id**, not @handle.

- `x_whoami` → your own `data.id`, `data.username`. Call it **once** at the start of a session and reuse the id for `x_home_timeline`, `x_like_post`, and `x_repost` (their `user_id` must be *you*).
- `x_get_user` (by @handle) → that person's `data.id`, for `x_user_posts` / `x_mentions`.

## Pick the tool

Read (each returned post is billed — see Cost):
- `x_search_posts` — recent posts (last 7 days). `query` supports `from:user`, `#tag`, `lang:en`, `-filter:retweets`.
- `x_get_post` — one post by id, with author.
- `x_user_posts` — a person's recent posts (by their numeric id).
- `x_mentions` — posts mentioning a user (by their numeric id).
- `x_home_timeline` — your reverse-chronological home feed (`user_id` = you).
- `x_whoami` / `x_get_user` — identity / handle → id.

Write — posts are public; show exact text and confirm before sending:
- `x_create_post` — post; optional `reply_to_post_id` makes it a reply. Report the new post id on success.
- `x_delete_post` — delete your own post (irreversible; confirm the target).
- `x_like_post` / `x_repost` — engage with a post (`user_id` = you, `post_id` = target).

## Cost — X API is pay-per-use, act accordingly

Every call spends real credits on the user's X developer account:

- **Reads bill per post returned** (~$0.005 each). Keep `max_results` at the default 10 unless the user asks for more. Reads return `meta.next_token`; page only on explicit request — each page is a separate charge. Do not loop pages to "be thorough."
- **A post whose text contains a URL costs ~13× a plain post** (~$0.20 vs ~$0.015). Warn the user before posting link-bearing text.
- Likes/reposts/deletes are cheap but still billed. Don't bulk-engage without intent.

## Errors — never fall back to the browser

- **401** → the connection expired; tell the user to reconnect X on the Fermix setup page. Don't loop.
- **403** → a missing scope (reconnect) or an Enterprise-only feature (e.g. quote posts) — say which; don't retry.
- **429** → either a rate-limit (wait for the window, then retry once) or `UsageCapExceeded`/credits exhausted (retrying is useless — tell the user to add credits at console.x.com).
- If the `x_*` tools aren't listed at all, the plugin isn't connected — tell the user to connect X on the setup page.

## Not supported (don't claim these)

Media/image upload, DMs, bookmarks, follows/blocks/mutes, quote posts (X gates quoting to Enterprise), and full-archive search beyond 7 days.
