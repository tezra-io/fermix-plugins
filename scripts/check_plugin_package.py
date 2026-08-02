#!/usr/bin/env python3
"""Pack a plugin the way the release does, then boundary-check the archive.

Usage:
  check_plugin_package.py plugins/<name> [plugins/<other> …]

Builds a throwaway tarball with the release layout (`tar -C plugins/<name> -czf
… .`, manifest at the archive root), runs the archive-listing content-boundary
check over `tar -tzf`, and discards the tarball on every path. CI and
`release-plugin.yml` call this same script, so a mispacked artifact fails here
instead of after signing — or at every user's install.

For a `remote_mcp` (plugin_api 3) plugin the boundary is the data-only one: the
artifact carries manifest, docs, skills, and assets, and no `src/`, `bin/`,
ecosystem file, or executable.

Exit 0 = valid; exit 1 with every finding listed otherwise.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pluginlib  # noqa: E402


def _run(argv):
    result = subprocess.run(argv, capture_output=True, check=False)
    if result.returncode != 0:
        raise pluginlib.ValidationError(f"{' '.join(argv)}: {result.stderr.decode().strip()}")
    return result.stdout.decode()


def check_package(plugin_dir: Path):
    """Validate the dir, pack it, and boundary-check the packed listing."""
    manifest = pluginlib.validate_plugin_dir(plugin_dir)
    with tempfile.TemporaryDirectory(prefix="fermix-plugin-pack-") as tmp:
        tarball = Path(tmp) / f"{plugin_dir.name}.tar.gz"
        _run(["tar", "-C", str(plugin_dir), "-czf", str(tarball), "."])
        listing = _run(["tar", "-tzf", str(tarball)]).splitlines()
        packed_bytes = tarball.stat().st_size
    errors = pluginlib.check_archive_listing(
        listing,
        has_runtime="runtime" in manifest,
        remote=pluginlib.is_remote_manifest(manifest),
    )
    return errors, len([line for line in listing if line.strip()]), packed_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plugin_dirs", nargs="+", type=Path)
    args = parser.parse_args()

    failures = []
    for plugin_dir in args.plugin_dirs:
        try:
            errors, members, packed_bytes = check_package(plugin_dir)
        except pluginlib.ValidationError as err:
            failures.append(str(err))
            continue
        if errors:
            failures.append(f"{plugin_dir} (packaged archive):\n  - " + "\n  - ".join(errors))
            continue
        print(f"ok: packaged {plugin_dir} ({members} members, {packed_bytes} bytes)")

    if failures:
        print("\nPACKAGE CHECK FAILED\n" + "\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
