#!/usr/bin/env python3
"""Build the signed catalog index from git tags + GitHub Releases.

The index is DERIVED state — never hand-edited, never committed. Source of
truth: plugin manifests at their release tags (`git show <tag>:plugins/...`)
plus the release assets (tarball URL + .sha256). A tag without a release, or a
release missing its .sha256, is skipped with a loud warning (nothing to
install). Yanked versions come from plugins/<name>/yanked.json at HEAD.

Usage: build_index.py [--out index.json]
Requires: git (full tag history) and an authenticated `gh`.
"""

import argparse
import base64
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pluginlib  # noqa: E402

TAG_RE = re.compile(r"^(?P<name>[a-z][a-z0-9_]{0,63})/v(?P<version>\d+\.\d+\.\d+)$")


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {result.stderr.strip()}")
    return result.stdout


def plugin_tags():
    """{name: [version, ...]} from tags shaped <name>/v<semver>."""
    tags = {}
    for line in run(["git", "tag", "-l"]).splitlines():
        match = TAG_RE.match(line.strip())
        if match:
            tags.setdefault(match["name"], []).append(match["version"])
    return tags


def semver_key(version):
    return tuple(int(part) for part in version.split("."))


def release_artifact(name, version):
    """{url, sha256, sig_url, cert_url, published_at} or None (warn + skip)."""
    tag = f"{name}/v{version}"
    try:
        raw = run(["gh", "release", "view", tag, "--json", "assets,publishedAt"])
    except RuntimeError as err:
        print(f"warning: skipping {tag} — no release ({err})", file=sys.stderr)
        return None
    release = json.loads(raw)
    urls = {asset["name"]: asset["url"] for asset in release["assets"]}
    tarball = f"{name}-{version}.tar.gz"
    missing = [n for n in (tarball, f"{tarball}.sha256", f"{tarball}.sig", f"{tarball}.pem") if n not in urls]
    if missing:
        print(f"warning: skipping {tag} — release missing assets: {missing}", file=sys.stderr)
        return None
    sha_line = run(["gh", "release", "download", tag, "--pattern", f"{tarball}.sha256", "--output", "-"])
    return {
        "target": "any",
        "url": urls[tarball],
        "sha256": sha_line.split()[0],
        "sig_url": urls[f"{tarball}.sig"],
        "cert_url": urls[f"{tarball}.pem"],
        "published_at": release["publishedAt"],
    }


def manifest_at(name, version):
    raw = pluginlib.git_show(f"{name}/v{version}:plugins/{name}/plugin.json")
    return json.loads(raw)


def inline_logo(name, version, manifest):
    rel = (manifest.get("interface") or {}).get("logo")
    if not rel:
        return None
    data = pluginlib.git_show(f"{name}/v{version}:plugins/{name}/{rel}")
    if len(data) > pluginlib.MAX_LOGO_BYTES:
        raise RuntimeError(f"{name}/v{version}: logo {rel} exceeds {pluginlib.MAX_LOGO_BYTES} bytes")
    mime = pluginlib.MIME_BY_EXT[Path(rel).suffix.lower()]
    return {"mime": mime, "data_base64": base64.b64encode(data).decode()}


def yanked_versions(name):
    path = Path("plugins") / name / "yanked.json"
    if not path.is_file():
        return []
    yanked = json.loads(path.read_text())
    if not isinstance(yanked, list) or not all(isinstance(v, str) for v in yanked):
        raise RuntimeError(f"{path}: must be a JSON array of version strings")
    return yanked


def plugin_entry(name, versions):
    """Index entry for one plugin, or None if no version has a usable release."""
    released = []
    for version in sorted(versions, key=semver_key, reverse=True):
        artifact = release_artifact(name, version)
        if artifact is None:
            continue
        manifest = manifest_at(name, version)
        released.append((version, manifest, artifact))
    if not released:
        print(f"warning: {name} has tags but no usable release — omitted", file=sys.stderr)
        return None
    latest_version, latest_manifest, _ = released[0]
    interface = latest_manifest.get("interface") or {}
    rails = sorted({tool.get("rail", "http") for tool in latest_manifest.get("tools", [])})
    return {
        "name": name,
        "display_name": latest_manifest["display_name"],
        "category": latest_manifest["category"],
        "description": latest_manifest["description"],
        "short_description": interface.get("short_description"),
        "developer_name": interface.get("developer_name"),
        "brand_color": interface.get("brand_color"),
        "logo": inline_logo(name, latest_version, latest_manifest),
        "auth_type": (latest_manifest.get("auth") or {}).get("type"),
        "rails": rails,
        "latest": latest_version,
        "yanked": yanked_versions(name),
        "versions": [
            {
                "version": version,
                "published_at": artifact.pop("published_at"),
                "min_core_version": manifest["min_core_version"],
                "plugin_api": manifest["plugin_api"],
                "artifacts": [artifact],
            }
            for version, manifest, artifact in released
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("index.json"))
    args = parser.parse_args()

    entries = []
    for name, versions in sorted(plugin_tags().items()):
        entry = plugin_entry(name, versions)
        if entry:
            entries.append(entry)

    index = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "plugins": entries,
    }
    args.out.write_text(json.dumps(index, indent=2) + "\n")
    print(f"wrote {args.out}: {len(entries)} plugin(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
