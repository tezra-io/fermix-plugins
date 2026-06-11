---
name: github-plugin
description: Use for ANY GitHub request — repos, issues, pull requests, github.com or api.github.com URLs — to list, get, search, or triage, and to open issues or comment. Hits the GitHub REST API directly via the Fermix GitHub plugin.
---

# GitHub

Use the `github_*` tools for anything on GitHub — repos, issues, pull requests, or a `github.com`/`api.github.com` link. Do NOT use the browser or web search for GitHub; these tools call the REST API directly, return clean data, and need no page scraping.

## Pick the tool

- Identity: `github_get_me` — resolve "my"/"me" to a login before searching.
- Repos: `github_list_repos` (the user's own) · `github_search_repos` (anyone's, by `q`).
- Issues in a known repo: `github_list_issues` (note: GitHub's issues list also includes PRs) · `github_get_issue` for one issue's full body.
- PRs in a known repo: `github_list_pull_requests` · `github_get_pull_request` for one PR.
- Don't know the repo, or filtering by author/text/label across repos: `github_search_issues` with `q` qualifiers.
- Writes (confirm first): `github_create_issue`, `github_add_issue_comment`.

List/get tools take `owner` + `repo` (and `number`); they are cheaper and ordered. Reach for search only when you lack the repo or need cross-repo filtering.

## Search `q` qualifiers

Free text plus space-separated qualifiers:
- `repo:owner/name`, `is:open`/`is:closed`, `is:issue`/`is:pr`
- `author:login`, `assignee:login`, `label:"bug"` (quote multi-word), `created:>2026-01-01`
- repos: `user:login`, `org:name`, `language:elixir`, `stars:>100`

Example — open PRs by the user in one repo: `q: "repo:acme/api is:pr is:open author:<login>"`.

## Write etiquette

`github_create_issue` and `github_add_issue_comment` post publicly under the user's account and notify others. Before calling either, show the exact `owner/repo`, title/body, and labels, and get explicit confirmation. Don't alter approved content.

## Access breadth

The connection holds the classic `repo` scope — read+write on every repo the user can access, including private code. The v1 tools only expose issue/PR/repo ops; stay inside what the user asked for, but be honest that the token is broad.

## Notes

- Pagination is page-number based, `per_page` ≤ 100 (default 30), no auto-paging. Exactly `per_page` items may mean more pages; fetch the next `page` and flag partial results. Keep `per_page` small (10–30).
- No file/code contents, commits, branches, reviews, merges, issue editing/closing, or repo creation. Don't claim those; point the user to github.com.
- If the `github_*` tools aren't available, the plugin isn't connected — tell the user to connect GitHub on the Fermix setup page. If a call returns an auth error, say to reconnect; don't retry or fall back to the browser.
