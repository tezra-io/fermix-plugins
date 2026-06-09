# Hacker News

Keyless Fermix plugin for Hacker News, backed by the public
[Algolia HN Search API](https://hn.algolia.com/api) (`https://hn.algolia.com/api/v1`).
No auth, no scopes — `"auth": {"type": "none"}`.

## Tools

| Tool | What it does |
|---|---|
| `hackernews_search_stories` | Search stories by keyword (`query`, optional `limit`, default 10) |
| `hackernews_front_page` | List the stories currently on the front page (optional `limit`, default 30) |

Both ride the declarative `http` rail and return per-story
`title`, `url`, `author`, `points`, `num_comments`, `created_at`, `objectID`.

## Releasing

Tag a merged commit `hackernews/v<version>` (matching `plugin.json`'s
`version`) and push the tag — `release-plugin.yml` validates, packs, signs,
publishes the release, and regenerates the signed catalog index.
