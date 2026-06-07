"""Shared plugin manifest + artifact validation for CI and the release pipeline.

Mirrors the install-time rules in the Fermix core decoder (M8 design §5.2/§7.2):
this is the publish-side gate; core re-validates everything at install. Keep the
two in sync — anything loosened here still refuses at install.
"""

import json
import re
import subprocess
from pathlib import Path

SCHEMA_VERSION = 2
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
MAX_TOOL_DESCRIPTION_BYTES = 100
MAX_LOGO_BYTES = 16 * 1024

AUTH_TYPES = {"none", "oauth2", "api_key"}
RAILS = {"http", "mcp"}
RUNTIME_KINDS = {"node", "python", "binary", "escript"}
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

# Content-boundary allowlist: the top level of a plugin dir / artifact may
# contain ONLY these entries. Proves "only this plugin's code/deps are in the
# artifact" — enforced here (CI, pre-sign) and again by the Fermix installer.
ALLOWED_TOP_LEVEL = {
    "plugin.json",
    "skills",
    "assets",
    "bin",
    "src",
    "CHANGELOG.md",
    "README.md",
    "LICENSE",
    "yanked.json",
}
# Permitted only when the manifest declares a runtime block (mcp rail).
RUNTIME_ECOSYSTEM_FILES = {
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "uv.lock",
    "requirements.txt",
    "mix.exs",
    "mix.lock",
}

MIME_BY_EXT = {".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


class ValidationError(Exception):
    """A plugin failed validation; message lists every finding."""


def load_manifest(plugin_dir: Path) -> dict:
    manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.is_file():
        raise ValidationError(f"{plugin_dir}: missing plugin.json at the plugin root")
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as err:
        raise ValidationError(f"{manifest_path}: invalid JSON — {err}") from err
    if not isinstance(manifest, dict):
        raise ValidationError(f"{manifest_path}: manifest must be a JSON object")
    return manifest


def validate_plugin_dir(plugin_dir: Path) -> dict:
    """Validate one plugin directory. Returns the manifest; raises ValidationError."""
    manifest = load_manifest(plugin_dir)
    errors = []
    errors += _validate_top_fields(manifest, plugin_dir)
    errors += _validate_auth(manifest)
    errors += _validate_tools(manifest)
    errors += _validate_runtime(manifest)
    errors += _validate_skills(manifest, plugin_dir)
    errors += _validate_interface(manifest, plugin_dir)
    errors += check_boundary(
        [p.name for p in plugin_dir.iterdir()], has_runtime="runtime" in manifest
    )
    if errors:
        raise ValidationError(f"{plugin_dir}:\n  - " + "\n  - ".join(errors))
    return manifest


def check_boundary(top_level_entries, has_runtime: bool):
    """Content-boundary allowlist over top-level entries (dir or archive).

    Anything not on the allowlist is rejected — including repo-level dotfiles
    like ``.git``, ``.github``, and ``.gitignore``. Core's installer rejects
    those at install time, so the publish side must reject them too; otherwise a
    mispacked archive could be signed and published only to fail at install.
    """
    allowed = ALLOWED_TOP_LEVEL | (RUNTIME_ECOSYSTEM_FILES if has_runtime else set())
    return [
        f"top-level entry {entry!r} violates the content-boundary allowlist "
        f"(allowed: {', '.join(sorted(allowed))})"
        for entry in sorted(set(top_level_entries))
        if entry not in allowed
    ]


def check_archive_listing(listing_lines, has_runtime: bool):
    """Boundary check over `tar -tzf` output: every member must sit under an
    allowed top-level entry, and plugin.json must be at the archive root."""
    top = set()
    saw_manifest = False
    for raw in listing_lines:
        member = raw.strip().lstrip("./")
        if not member:
            continue
        head = member.split("/", 1)[0]
        top.add(head)
        if member == "plugin.json":
            saw_manifest = True
    errors = check_boundary(top, has_runtime)
    if not saw_manifest:
        errors.append("plugin.json is not at the archive root (pack with `tar -C plugins/<name> … .`)")
    return errors


def _validate_top_fields(manifest, plugin_dir):
    errors = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION} for distributed plugins")
    name = manifest.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        errors.append("name must match ^[a-z][a-z0-9_]{0,63}$")
    elif name.startswith("mcp_"):
        errors.append("name must not start with mcp_ (reserved for operator MCP servers)")
    elif name != plugin_dir.name:
        errors.append(f"name {name!r} must equal the directory name {plugin_dir.name!r}")
    for field in ("display_name", "description", "category"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            errors.append(f"{field} must be a non-empty string")
    for field in ("version", "min_core_version"):
        if not isinstance(manifest.get(field), str) or not SEMVER_RE.match(manifest[field]):
            errors.append(f"{field} must be semver MAJOR.MINOR.PATCH")
    if not isinstance(manifest.get("plugin_api"), int):
        errors.append("plugin_api must be an integer")
    return errors


def _validate_auth(manifest):
    auth = manifest.get("auth")
    if not isinstance(auth, dict):
        return ["auth block is required (use {\"type\": \"none\"} for no auth)"]
    errors = []
    auth_type = auth.get("type")
    if auth_type not in AUTH_TYPES:
        errors.append(f"auth.type must be one of {sorted(AUTH_TYPES)}")
    if auth_type == "oauth2":
        scopes = auth.get("scopes")
        if not isinstance(scopes, list) or not scopes or not all(isinstance(s, str) and s for s in scopes):
            errors.append("oauth2 plugins must declare a non-empty auth.scopes list")
        if not isinstance(manifest.get("health_check"), dict):
            errors.append("oauth2 plugins must declare a health_check")
    if auth_type == "api_key":
        for field in ("key_name", "header", "prompt"):
            if not isinstance(auth.get(field), str) or not auth[field].strip():
                errors.append(f"api_key plugins must declare auth.{field}")
    return errors


def _validate_tools(manifest):
    tools = manifest.get("tools")
    if not isinstance(tools, list) or not tools:
        return ["tools must be a non-empty list"]
    errors = []
    name = manifest.get("name") or ""
    auth = manifest.get("auth") or {}
    seen = set()
    for tool in tools:
        if not isinstance(tool, dict):
            errors.append("each tool must be an object")
            continue
        errors += _validate_tool(tool, name, auth, seen)
    return errors


def _validate_tool(tool, plugin_name, auth, seen):
    errors = []
    tool_name = tool.get("name", "")
    label = tool_name or "<unnamed tool>"
    if not isinstance(tool_name, str) or not TOOL_NAME_RE.match(tool_name):
        errors.append(f"{label}: tool name must match ^[A-Za-z0-9_-]{{1,64}}$")
    elif not tool_name.startswith(f"{plugin_name}_"):
        errors.append(f"{label}: tool name must be namespaced {plugin_name}_…")
    if tool_name in seen:
        errors.append(f"{label}: duplicate tool name")
    seen.add(tool_name)
    description = tool.get("description", "")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{label}: description is required")
    elif len(description.encode()) > MAX_TOOL_DESCRIPTION_BYTES:
        errors.append(f"{label}: description exceeds {MAX_TOOL_DESCRIPTION_BYTES} bytes")
    if not isinstance(tool.get("read_only"), bool):
        errors.append(f"{label}: read_only must be a boolean")
    rail = tool.get("rail", "http")
    if rail not in RAILS:
        errors.append(f"{label}: rail must be one of {sorted(RAILS)}")
    if rail == "http":
        errors += _validate_http_tool(tool, label)
    if auth.get("type") == "oauth2":
        scopes = tool.get("requires_scopes")
        if not isinstance(scopes, list) or not scopes:
            errors.append(f"{label}: oauth2 tools must declare requires_scopes")
        elif not set(scopes) <= set(auth.get("scopes") or []):
            errors.append(f"{label}: requires_scopes must be a subset of auth.scopes")
    return errors


def _validate_http_tool(tool, label):
    errors = []
    parameters = tool.get("parameters")
    if not isinstance(parameters, dict) or parameters.get("type") != "object":
        errors.append(f"{label}: http tools need a parameters object schema (type: object)")
    request = tool.get("request")
    if not isinstance(request, dict):
        return errors + [f"{label}: http tools need a request template"]
    if request.get("method") not in HTTP_METHODS:
        errors.append(f"{label}: request.method must be one of {sorted(HTTP_METHODS)}")
    errors += _validate_request_url(request.get("url"), label)
    return errors


def _validate_request_url(url, label):
    """SSRF guard, publish side: https only; no placeholder in scheme/host."""
    if not isinstance(url, str) or not url:
        return [f"{label}: request.url is required"]
    if not url.startswith("https://"):
        return [f"{label}: request.url must be https://"]
    host = url[len("https://"):].split("/", 1)[0]
    if "{" in host or not host:
        return [f"{label}: request.url host must be a static literal (no placeholders)"]
    return []


def _validate_runtime(manifest):
    tools = manifest.get("tools") or []
    needs_runtime = any(isinstance(t, dict) and t.get("rail") == "mcp" for t in tools)
    runtime = manifest.get("runtime")
    if needs_runtime and not isinstance(runtime, dict):
        return ["a runtime block is required when any tool has rail: mcp"]
    if runtime is None:
        return []
    errors = []
    if not needs_runtime:
        errors.append("runtime block declared but no tool has rail: mcp")
    if runtime.get("kind") not in RUNTIME_KINDS:
        errors.append(f"runtime.kind must be one of {sorted(RUNTIME_KINDS)}")
    if not isinstance(runtime.get("command"), str) or not runtime["command"].strip():
        errors.append("runtime.command is required")
    if not isinstance(runtime.get("vendored"), bool):
        errors.append("runtime.vendored must be a boolean")
    return errors


def _validate_skills(manifest, plugin_dir):
    errors = []
    for skill in manifest.get("skills") or []:
        if not isinstance(skill, dict) or not skill.get("name") or not skill.get("path"):
            errors.append("each skill needs name and path")
            continue
        if skill["name"] == manifest.get("name"):
            errors.append(f"skill {skill['name']!r} must not equal the plugin name")
        if not (plugin_dir / skill["path"]).is_file():
            errors.append(f"skill path {skill['path']!r} does not exist")
    return errors


def _validate_interface(manifest, plugin_dir):
    errors = []
    interface = manifest.get("interface") or {}
    for field in ("icon", "logo"):
        rel = interface.get(field)
        if rel is None:
            continue
        path = plugin_dir / rel
        if not path.is_file():
            errors.append(f"interface.{field} {rel!r} does not exist")
            continue
        if Path(rel).suffix.lower() not in MIME_BY_EXT:
            errors.append(f"interface.{field} {rel!r} must be one of {sorted(MIME_BY_EXT)}")
        if field == "logo" and path.stat().st_size > MAX_LOGO_BYTES:
            errors.append(f"interface.logo exceeds {MAX_LOGO_BYTES} bytes (index-inlined; keep it small)")
    return errors


def git_show(ref_path: str) -> bytes:
    """`git show <ref>:<path>` as bytes; raises ValidationError on failure."""
    result = subprocess.run(["git", "show", ref_path], capture_output=True, check=False)
    if result.returncode != 0:
        raise ValidationError(f"git show {ref_path}: {result.stderr.decode().strip()}")
    return result.stdout
