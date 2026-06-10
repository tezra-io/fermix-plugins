# GitHub plugin

Declarative (http-rail) Fermix plugin for GitHub: repositories, issues, and pull requests via `api.github.com`. Pure `plugin.json` — no code, no runtime.

## Auth

OAuth2 browser login against an **operator-registered GitHub OAuth App**:

1. Create an OAuth App at GitHub → Settings → Developer settings → OAuth Apps.
2. Set the authorization callback URL to `http://127.0.0.1/auth/callback` — GitHub port-wildcards loopback literals, so any runtime port Fermix picks will match.
3. Paste the client ID + secret into Fermix (setup page or config); the secret is stored in the OS keychain.

Scopes requested: `read:user`, `repo`. **Note the breadth:** classic `repo` is GitHub's only scope covering private-repo issues/PRs and it also grants code read/write across everything the user can access. Fermix only exposes the tools below, but the token itself is broad. GitHub OAuth tokens do not expire and have no refresh token; a revoked token surfaces as a reauthorize error.

## Tools

| Tool | What it does |
|---|---|
| `github_get_me` | Authenticated user profile |
| `github_list_repos` | List the user's repositories |
| `github_list_issues` | List issues in a repository |
| `github_get_issue` | Get one issue |
| `github_create_issue` | Create an issue (write) |
| `github_add_issue_comment` | Comment on an issue/PR (write) |
| `github_list_pull_requests` | List pull requests in a repository |
| `github_get_pull_request` | Get one pull request |
| `github_search_issues` | Search issues/PRs across GitHub |
| `github_search_repos` | Search repositories across GitHub |
