# plugins/

One directory per plugin. Each plugin is **self-contained**: its own manifest,
skills, assets, and (for `mcp`-rail plugins) its own code and dependency files.
There is no shared build across plugins, and nothing here is part of the
`apps/` Elixir umbrella.

## Anatomy

```
plugins/<name>/
  plugin.json          # REQUIRED — the manifest, at the plugin ROOT (schema_version 2)
  skills/<skill>/SKILL.md
  assets/{logo.png, icon.svg}
  src/                 # mcp-rail plugins only: server source
  bin/                 # mcp-rail plugins only: vendored builds (release artifact)
  CHANGELOG.md
  README.md            # optional
  LICENSE              # optional (repo LICENSE applies otherwise)
  yanked.json          # optional: ["1.0.1", ...] versions to mark yanked in the index
```

The top level of a plugin dir may contain **only** the entries above (plus the
ecosystem files a `runtime` block implies, e.g. `package.json`). CI and the
Fermix installer both enforce this allowlist — an artifact must contain only
this plugin's code and deps.

## Releasing a plugin

1. Bump `version` in `plugin.json` and update `CHANGELOG.md`.
2. PR → review → merge to `main`.
3. Tag the merge commit `<name>/v<version>` (must equal the manifest version)
   and push the tag.

`release-plugin.yml` then validates the manifest, packs
`tar -C plugins/<name> … .` (manifest at the archive root), checks the content
allowlist against the packed file list, signs with cosign (keyless OIDC),
attaches `<name>-<version>.tar.gz` + `.sha256` + `.sig` + `.pem` to a GitHub
Release for the tag, and regenerates the signed catalog `index.json` on the
rolling `index` release.

Adding a plugin requires **no change in the fermix repo** — the catalog entry
(name, logo, description, compat floors) is derived from `plugin.json` by CI,
and installed daemons pick it up on their next index refresh.

## Validation

```sh
python3 scripts/validate_plugin.py --all          # every plugin dir
python3 scripts/validate_plugin.py plugins/github # one plugin
```

The same checks run in CI on every PR and again (plus the archive-list check)
at release time, before signing. Full manifest/schema reference:
`fermix` repo, `docs/design/MILESTONE_8_PLUGIN_DISTRIBUTION.md` §5.
