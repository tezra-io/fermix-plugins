#!/usr/bin/env python3
"""Validate plugin dirs (CI) and packed artifacts (release, pre-sign).

Usage:
  validate_plugin.py --all                          # every dir under plugins/
  validate_plugin.py plugins/<name>                 # one plugin dir
  validate_plugin.py --archive listing.txt plugins/<name>
                                                    # boundary-check a `tar -tzf`
                                                    # listing against the manifest

Exit 0 = valid; exit 1 with every finding listed otherwise.

Draft manifests
---------------
Some manifest fields can only come from an authenticated capture against the
live upstream — a remote MCP tool's `parameters`, `output_schema`,
`upstream_annotations`, and the `descriptor_sha256` that binds them (M27 §12
Stage 0). Until that capture lands, the manifest carries the literal string
`STAGE0_PENDING` in each such field and declares `"draft": true`.

A draft is a manifest STATE, not a fallback code path. The grammar is never
relaxed for it, no value is guessed on its behalf, and it is never installable
or releasable — a fabricated 64-hex descriptor would validate here and then fail
confusingly at runtime, which is the exact failure the signed contract exists to
prevent. The three entry points treat that state differently:

  --all             report SKIPPED so one pending capture cannot block every
                    other plugin's CI.
  plugins/<name>    run the full grammar and list precisely which fields the
                    capture still owes.
  --archive         refuse outright; the release path never packs a draft.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pluginlib  # noqa: E402

DRAFT_SENTINEL = "STAGE0_PENDING"
# JSON nests shallowly here; the cap keeps the sentinel walk terminating on any
# input rather than trusting the document's shape.
MAX_MANIFEST_DEPTH = 32


def is_draft(manifest) -> bool:
    """True when the manifest declares itself pre-capture (see module docstring)."""
    return isinstance(manifest, dict) and manifest.get("draft") is True


def pending_fields(node, path="", depth=0):
    """Every JSON path under `node` whose value is the Stage-0 sentinel."""
    if depth > MAX_MANIFEST_DEPTH:
        return [f"{path or '/'} (not scanned: nesting exceeds {MAX_MANIFEST_DEPTH})"]
    if node == DRAFT_SENTINEL:
        return [path or "/"]
    if isinstance(node, dict):
        return [p for key, value in node.items() for p in pending_fields(value, f"{path}/{key}", depth + 1)]
    if isinstance(node, list):
        return [p for i, value in enumerate(node) for p in pending_fields(value, f"{path}/{i}", depth + 1)]
    return []


def draft_findings(plugin_dir, pending):
    """The pending-field inventory plus the unrelaxed grammar's own findings."""
    lines = [f"{plugin_dir}: DRAFT — Stage 0 authenticated capture pending"]
    lines += [f"  - pending: {path}" for path in pending]
    try:
        pluginlib.validate_plugin_dir(plugin_dir)
    except pluginlib.ValidationError as err:
        return "\n".join(lines + [f"  - grammar (never relaxed for a draft): {err}"])
    return "\n".join(lines + ["  - grammar: clean; replace the placeholders above and drop \"draft\": true"])


def validate_one(plugin_dir, skip_drafts):
    """Validate one plugin dir. Prints its status line; returns its findings."""
    manifest = pluginlib.load_manifest(plugin_dir)
    if not is_draft(manifest):
        pluginlib.validate_plugin_dir(plugin_dir)
        print(f"ok: {plugin_dir}")
        return []
    pending = pending_fields(manifest)
    if not pending:
        # Otherwise `draft: true` would be a permanent CI skip switch.
        return [
            f"{plugin_dir}: draft: true but no {DRAFT_SENTINEL} placeholder remains — "
            f"drop the draft flag now that the capture has landed"
        ]
    if skip_drafts:
        print(
            f"SKIPPED (draft — Stage 0 capture pending): {plugin_dir} "
            f"({len(pending)} pending fields; run `validate_plugin.py {plugin_dir}` to list them)"
        )
        return []
    return [draft_findings(plugin_dir, pending)]


def validate_dirs(dirs, skip_drafts):
    failures = []
    for plugin_dir in dirs:
        try:
            failures += validate_one(plugin_dir, skip_drafts)
        except pluginlib.ValidationError as err:
            failures.append(str(err))
    return failures


def validate_archive(listing_path, plugin_dir):
    manifest = pluginlib.load_manifest(plugin_dir)
    if is_draft(manifest):
        # A signature is not revocable by editing a file, so the refusal lands
        # before anything is read, packed, or hashed.
        return [
            f"{plugin_dir}: refusing to release a draft manifest — Stage 0 capture is pending "
            f"(drop \"draft\": true only once every {DRAFT_SENTINEL} placeholder is replaced)"
        ]
    manifest = pluginlib.validate_plugin_dir(plugin_dir)
    lines = Path(listing_path).read_text().splitlines()
    errors = pluginlib.check_archive_listing(
        lines,
        has_runtime="runtime" in manifest,
        remote=pluginlib.is_remote_manifest(manifest),
    )
    if errors:
        return [f"{listing_path} (archive of {plugin_dir}):\n  - " + "\n  - ".join(errors)]
    print(f"ok: archive listing {listing_path}")
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plugin_dirs", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true", help="validate every dir under plugins/")
    parser.add_argument("--archive", type=Path, help="tar -tzf listing file to boundary-check")
    args = parser.parse_args()

    if args.archive:
        if len(args.plugin_dirs) != 1:
            parser.error("--archive requires exactly one plugin dir")
        try:
            failures = validate_archive(args.archive, args.plugin_dirs[0])
        except pluginlib.ValidationError as err:
            failures = [str(err)]
    elif args.all:
        dirs = sorted(p for p in Path("plugins").iterdir() if p.is_dir())
        if not dirs:
            print("ok: no plugins yet")
            return 0
        failures = validate_dirs(dirs, skip_drafts=True)
    elif args.plugin_dirs:
        failures = validate_dirs(args.plugin_dirs, skip_drafts=False)
    else:
        parser.error("pass plugin dirs, --all, or --archive")

    if failures:
        print("\nVALIDATION FAILED\n" + "\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
