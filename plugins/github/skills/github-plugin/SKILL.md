---
name: github-plugin
description: Browse, search, and triage GitHub repositories, issues, and pull requests, and create issues or comments (confirming writes) through the Fermix GitHub plugin.
---

# GitHub

Use this skill when the GitHub plugin is enabled and connected. Answer questions about repos, issues, and pull requests from the read tools; never publish anything (issue, comment) without explicit intent.

## Tools

Read:
- `github_get_me` (read-only) — the authenticated user's profile (`login`, `name`, `email`, `html_url`). Use it to resolve "my"/"me" into a login before searching.
- `github_list_repos` (read-only) — repositories the user can access. Args: `visibility` (`all`/`public`/`private`), `sort` (`created`/`updated`/`pushed`/`full_name`), `per_page`, `page`.
- `github_list_issues` (read-only) — issues in one repo. Args: `owner`, `repo`, optional `state` (`open`/`closed`/`all`), `labels` (comma-separated), `per_page`, `page`. Note: GitHub's issues list also includes pull requests.
- `github_get_issue` (read-only) — one issue with full body. Args: `owner`, `repo`, `number`.
- `github_list_pull_requests` (read-only) — PRs in one repo. Args: `owner`, `repo`, optional `state`, `per_page`, `page`.
- `github_get_pull_request` (read-only) — one PR with full body. Args: `owner`, `repo`, `number`.
- `github_search_issues` (read-only) — search issues/PRs across all of GitHub. Args: `q`, `per_page`, `page`.
- `github_search_repos` (read-only) — search repositories. Args: `q`, `per_page`, `page`.

Write (public actions — confirm first):
- `github_create_issue` — open a new issue. Args: `owner`, `repo`, `title`, optional `body` (Markdown), `labels` (array of names).
- `github_add_issue_comment` — comment on an issue or PR. Args: `owner`, `repo`, `number`, `body` (Markdown).

## List vs. search

- **Know the repo?** Use the list/get tools (`github_list_issues`, `github_list_pull_requests`) — they are cheaper and ordered.
- **Don't know the repo, or filtering by author/text/label across repos?** Use `github_search_issues` with `q` qualifiers.

## Search `q` qualifier syntax

Combine free text with qualifiers, space-separated:

- `repo:owner/name` — limit to one repository
- `is:open` / `is:closed`, `is:issue` / `is:pr` — state and kind
- `author:login`, `assignee:login`, `mentions:login` — people (use `github_get_me` for the user's own login)
- `label:"bug"` — label (quote multi-word labels)
- `created:>2026-01-01`, `updated:>=2026-06-01` — date ranges
- repos (`github_search_repos`): `user:login`, `org:name`, `language:elixir`, `stars:>100`

Example: open PRs by the user in one repo → `q: "repo:acme/api is:pr is:open author:<login>"`.

## Write etiquette

`github_create_issue` and `github_add_issue_comment` are **public actions** — they post under the user's account and notify other humans (watchers, mentioned users). Before calling either: show the exact `owner/repo`, title/body text, and labels, and get explicit confirmation. Never edit tone or content beyond what was approved.

## Access breadth

The connection carries the classic `repo` scope — it can read **and write** all repositories the user can access, including private ones and code. Fermix's v1 toolset only exposes the issue/PR/repo operations above, but be honest if asked: the token itself is broad. Stay inside what the user asked for.

## Pagination

GitHub list and search responses are page-number based and capped at `per_page` ≤ 100 (default 30). There is no automatic pagination: if a result set looks truncated (you got exactly `per_page` items), fetch the next `page` yourself, and say when results may be incomplete. Keep `per_page` small (10–30) unless the task needs a full sweep.

## Limitations

No file/code contents, no commits or branches, no reviews or merges, no issue editing or closing, no repo creation. Do not claim those actions; suggest the user does them on github.com.
