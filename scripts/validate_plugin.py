#!/usr/bin/env python3
"""Validate plugin dirs (CI) and packed artifacts (release, pre-sign).

Usage:
  validate_plugin.py --all                          # every dir under plugins/
  validate_plugin.py plugins/<name>                 # one plugin dir
  validate_plugin.py --archive listing.txt plugins/<name>
                                                    # boundary-check a `tar -tzf`
                                                    # listing against the manifest

Exit 0 = valid; exit 1 with every finding listed otherwise.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pluginlib  # noqa: E402


def validate_dirs(dirs):
    failures = []
    for plugin_dir in dirs:
        try:
            pluginlib.validate_plugin_dir(plugin_dir)
            print(f"ok: {plugin_dir}")
        except pluginlib.ValidationError as err:
            failures.append(str(err))
    return failures


def validate_archive(listing_path, plugin_dir):
    manifest = pluginlib.validate_plugin_dir(plugin_dir)
    lines = Path(listing_path).read_text().splitlines()
    errors = pluginlib.check_archive_listing(lines, has_runtime="runtime" in manifest)
    if errors:
        return [f"{listing_path} (archive of {plugin_dir}):\n  - " + "\n  - ".join(errors)]
    print(f"ok: archive listing {listing_path}")
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_dirs", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true", help="validate every dir under plugins/")
    parser.add_argument("--archive", type=Path, help="tar -tzf listing file to boundary-check")
    args = parser.parse_args()

    if args.archive:
        if len(args.plugin_dirs) != 1:
            parser.error("--archive requires exactly one plugin dir")
        failures = validate_archive(args.archive, args.plugin_dirs[0])
    elif args.all:
        dirs = sorted(p for p in Path("plugins").iterdir() if p.is_dir())
        if not dirs:
            print("ok: no plugins yet")
            return 0
        failures = validate_dirs(dirs)
    elif args.plugin_dirs:
        failures = validate_dirs(args.plugin_dirs)
    else:
        parser.error("pass plugin dirs, --all, or --archive")

    if failures:
        print("\nVALIDATION FAILED\n" + "\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
