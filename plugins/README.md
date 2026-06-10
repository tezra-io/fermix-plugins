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
  yanked.json          # optional: ["1.0.1", ...] versions to mark yanked in the catalog
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
allowlist against the packed file list, signs with cosign (keyless OIDC), and
attaches `<name>-<version>.tar.gz` + `.sha256` + `.sig` + `.pem` to a GitHub
Release for the tag.

4. To put the release in front of users, regenerate the **static catalog** in
   the fermix repo: run `python3 scripts/release/sync_plugin_catalog.py` there
   (it enumerates this repo's release tags, downloads + sha256- and
   cosign-verifies every artifact it pins, and rewrites
   `apps/fermix_core/priv/plugins/index.json`), then land that data change via
   a normal fermix PR. The catalog ships inside the next fermix release — there
   is no remote index and no refresh; daemons only ever read the bundled
   catalog, and artifacts are fetched (and re-verified) at install time from
   the GitHub Release published above.

## Validation

```sh
python3 scripts/validate_plugin.py --all          # every plugin dir
python3 scripts/validate_plugin.py plugins/github # one plugin
```

The same checks run in CI on every PR and again (plus the archive-list check)
at release time, before signing. Manifest/schema reference: the validation
source of truth is `scripts/pluginlib.py` here and
`FermixCore.Plugins.Registry.decode_manifest/2` in the fermix repo (the
installer and registry run the same rules).
