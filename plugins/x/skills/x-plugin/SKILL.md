---
name: x-plugin
description: Use for ANY X (Twitter) request — post, reply, delete, repost, search, or read timelines/mentions/users through the X API — and for what that API can't do.
---

# X (Twitter)

Start with the `x_*` tools for anything on X they cover. They call the X API directly — no login, no scraping.

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
- `x_create_post` — post; optional `reply_to_post_id` makes it a reply (X limits which replies it accepts — see below). Report the new post id on success.
- `x_delete_post` — delete your own post (irreversible; confirm the target).
- `x_repost` — repost a post (`user_id` = you, `post_id` = target).
- `x_like_post` — like a post. Only an Enterprise X app may; a pay-per-use app gets a 403, so like in the browser instead.

## What the API can't do

A pay-per-use X app cannot like, follow or unfollow, quote a post, block or unblock an account, report a post or account, or reply to someone else's post unless that post @mentions the user or quotes one of theirs. This plugin also has no DMs, bookmarks, mutes, media upload or full-archive search. Do these in the browser on x.com, in this conversation rather than a delegated skill run (whose browser has none of the user's sign-ins), and tell the user you are doing it there and why. Text you would post gets the same show-and-confirm as `x_create_post`, and a report is confirmed first; anything else the user asked for needs no extra confirmation.

## Cost — X API is pay-per-use, act accordingly

Every call spends real credits on the user's X developer account:

- **Reads bill per post returned** (~$0.005 each; ~$0.001 for the user's own posts and mentions). Keep `max_results` at the default 10 unless the user asks for more. Reads return `meta.next_token`; page only on explicit request — each page is a separate charge. Do not loop pages to "be thorough."
- **A post whose text contains a URL costs ~13× a plain post** (~$0.20 vs ~$0.015). Warn the user before posting link-bearing text.
- Reposts and deletes are billed too. Don't bulk-engage without intent.

## Errors

- **401** → the connection expired; tell the user to reconnect X on the Fermix setup page. Don't loop.
- **403** → a missing scope (reconnect) or a feature this X app's plan doesn't include — say which; don't retry.
- **429** → either a rate-limit (wait for the window, then retry once) or `UsageCapExceeded`/credits exhausted (retrying is useless — tell the user to add credits at console.x.com).
- If the `x_*` tools aren't listed at all, the plugin isn't connected — tell the user to connect X on the setup page.

When X refuses a call for a reason a retry or a reconnect won't change (a 403 for the plan, credits used up), do the task in the browser instead and say why.
