# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately by email to **[security@tezra.io](mailto:security@tezra.io)**.
The same address covers every Fermix repository.

Please include:

- a description of the issue and its impact,
- steps to reproduce (or a proof of concept),
- the affected version / commit, and
- any suggested remediation.

We aim to acknowledge reports within a few days and will coordinate a fix and
disclosure timeline with you. Never include real secrets (API keys, tokens) in
a report — redact them.

## Supported versions

Each plugin ships as its own release. The Fermix engine's plugin catalog pins
those releases, so a fix reaches users with the engine release that pins it.

## Scope

This repository holds Fermix plugins: integrations distributed separately from
the engine. Many of them hold OAuth tokens or API keys for the owner's
accounts.

For the Fermix engine's own boundary (secret handling, the sandbox, channel
ingress, signed upgrades), see the [Fermix security policy](https://github.com/tezra-io/fermix/blob/main/SECURITY.md).
