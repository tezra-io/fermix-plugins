# X (Twitter) plugin

Post, reply, delete, like, repost, search, and read X (Twitter) from Fermix.
Pure declarative `http`-rail plugin: nothing but `plugin.json`, a logo, and a
skill — no code, no runtime.

## Auth — your own X developer app

The plugin signs in with OAuth 2.0 (PKCE) against an app **you** register (one
time):

1. In the [X Developer Portal](https://developer.x.com/en/portal/dashboard),
   create a Project and an App.
2. Open the App's **User authentication settings** and set:
   - **App type: "Web App, Automated App or Bot"** — this is a *confidential*
     client and is the one that issues a Client Secret. (The "Native App" type
     issues no secret and fails OAuth with `unauthorized_client`.)
   - **Callback URI / Redirect URL** exactly `http://127.0.0.1:1459/auth/callback`
     — use the IP `127.0.0.1`, **not** `localhost` (X's portal accepts the IP
     literal but rejects `localhost`). X matches redirect URIs exactly, port
     included, so the port must be `1459` (Fermix binds it fixed, no fallback).
   - Website URL: anything you own.
3. Copy the **OAuth 2.0 Client ID and Client Secret** into the Fermix setup
   page (the secret is stored in your OS keychain). Token exchange uses HTTP
   Basic auth, handled by Fermix.

On Connect, X's consent screen lists the scopes below. Refresh tokens are
single-use (rotated each refresh) — Fermix persists the rotated token
automatically; if a refresh ever fails, reconnect on the setup page.

### Scopes requested

`tweet.read`, `users.read`, `tweet.write`, `like.write`, `offline.access`
(the last enables token refresh so you don't re-auth every two hours).

## Pricing — X API access is paid

X retired its free API tier in 2026; API access is **pay-per-use credits** you
buy in the [Developer Console](https://console.x.com). Rough current costs:
reads ~$0.005 per post returned, a post ~$0.015 (**~$0.20 if the text contains
a URL**), likes/reposts ~$0.015. The plugin defaults reads to 10 results and
never auto-paginates, and the skill tells the agent to keep calls small. Verify
current prices in the Console before relying on these figures.

## Tools

| Tool | What it does |
|---|---|
| `x_whoami` | Your user id, username, name (call once, reuse the id) |
| `x_get_user` | Look up a user by @username → numeric id + profile |
| `x_search_posts` | Search recent posts (last 7 days) |
| `x_get_post` | One post by id, with author |
| `x_user_posts` | A user's recent posts (by numeric id) |
| `x_mentions` | Posts mentioning a user (by numeric id) |
| `x_home_timeline` | Your reverse-chronological home feed |
| `x_create_post` | Post; optional reply to a post |
| `x_delete_post` | Delete one of your posts |
| `x_like_post` | Like a post |
| `x_repost` | Repost (retweet) a post |

Not included (yet): media upload, DMs, bookmarks, follows, and quote posts (X
gates quoting to Enterprise). The `x-plugin` skill teaches the agent the id
workflow, the cost guardrails, and the error/reconnect flow.
