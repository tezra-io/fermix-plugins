# plugins/

One directory per plugin. Each plugin is **self-contained**: its own manifest,
skills, assets, and — for a plugin that runs a **local** MCP server — its own
code and dependency files. There is no shared build across plugins, and nothing
here is part of the `apps/` Elixir umbrella.

## Anatomy

```
plugins/<name>/
  plugin.json          # REQUIRED — the manifest, at the plugin ROOT (schema_version 2)
  skills/<skill>/SKILL.md
  assets/{logo.png, icon.svg}
  src/                 # LOCAL mcp-rail plugins only: server source
  bin/                 # LOCAL mcp-rail plugins only: vendored builds (release artifact)
  CHANGELOG.md
  README.md            # optional
  LICENSE              # optional (repo LICENSE applies otherwise)
  yanked.json          # optional: ["1.0.1", ...] versions to mark yanked in the catalog
```

The top level of a plugin dir may contain **only** the entries above (plus the
ecosystem files a local `runtime` block implies, e.g. `package.json`). CI and
the Fermix installer both enforce this allowlist — an artifact must contain only
this plugin's code and deps.

`src/` and `bin/` belong to the *local process* a plugin may ship, not to the
`mcp` rail as such. A remote MCP plugin rides the same rail with no code at all.

## Three kinds of plugin

| Kind | `runtime` | Ships code? | Extra top-level entries |
|---|---|---|---|
| `http` rail | none | no | — |
| `mcp` rail, local process | `kind: node`/`python`/`binary`/`escript` | yes | `src/`, `bin/`, ecosystem files |
| `mcp` rail, remote service | `kind: remote_mcp` (`plugin_api: 3`) | **no** | none |

### Remote MCP plugins (`plugin_api: 3`)

A `remote_mcp` plugin declares a hosted Streamable-HTTP MCP endpoint; Fermix
connects to it directly. There is no local process, so the artifact is **data
only** — `plugin.json`, `README.md`, `CHANGELOG.md`, `LICENSE`, `assets/`,
`skills/`, `yanked.json`. No `src/`, no `bin/`, no `package.json` or other
ecosystem file, and no file with an executable mode bit. The validator refuses
all of them, in the directory and again in the packed archive.

Its `tools` list is an **enforcement boundary, not a preview**: each tool
carries a signed `descriptor_sha256` over the canonical (RFC 8785) descriptor,
and Fermix registers a tool only when the live upstream descriptor hashes to the
same value. The manifest also declares `tool_profiles`, `setup_tools`,
`resource_scope`, `budgets`, and `result_contract`. Full grammar: M27 §7.2,
§7.5, §7.6, §9.2 in the fermix repo — and `scripts/pluginlib.py`, which enforces
every rule.

`plugin_api: 3` is version-conditional and additive: a `plugin_api: 2` manifest
carrying any of those fields is **rejected**, not reinterpreted. `plugin_api: 2`
plugins are unaffected.

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
python3 scripts/validate_plugin.py --all              # every plugin dir
python3 scripts/validate_plugin.py plugins/github     # one plugin
python3 scripts/check_plugin_package.py plugins/*/    # pack each to a temp tarball
                                                      # and boundary-check the listing
python3 scripts/test_pluginlib.py                     # unit-test the validator itself
```

The same checks run in CI on every PR and again (plus the archive-list check)
at release time, before signing. Manifest/schema reference: the validation
source of truth is `scripts/pluginlib.py` here and
`FermixCore.Plugins.Registry.decode_manifest/2` in the fermix repo (the
installer and registry run the same rules).

`scripts/fixtures/` holds the cross-language golden fixtures — RFC 8785
canonicalization (which produces `descriptor_sha256`) and `tree_digest_v2` —
that pin this validator and Fermix core to identical bytes. See
`scripts/fixtures/README.md`.
