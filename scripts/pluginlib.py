"""Shared plugin manifest + artifact validation for CI and the release pipeline.

Mirrors the install-time rules in the Fermix core decoder (M8 design §5.2/§7.2):
this is the publish-side gate; core re-validates everything at install. Keep the
two in sync — anything loosened here still refuses at install.

M27 §7.2/§7.5/§7.6 add the `plugin_api: 3` remote-MCP grammar on top of the
schema-v2 shape. It is strictly version-conditional: a `plugin_api: 2` manifest
carrying any plugin-api-3-only field is rejected rather than silently accepted
under old semantics, and plugin-api-2 validation is unchanged.
"""

import base64
import hashlib
import ipaddress
import json
import re
import struct
import subprocess
import unicodedata
from pathlib import Path

SCHEMA_VERSION = 2
PLUGIN_API_REMOTE = 3
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CONFIG_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
PROFILE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_LABEL = r"[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?"
HOSTNAME_RE = re.compile(rf"^{_LABEL}(\.{_LABEL})*$")
REGEX_METACHARS = set("^$*+?()[]{}|\\")
MAX_TOOL_DESCRIPTION_BYTES = 100
MAX_LOGO_BYTES = 16 * 1024
MAX_HOSTNAME_BYTES = 253

AUTH_TYPES = {"none", "oauth2", "api_key"}
RAILS = {"http", "mcp"}
RUNTIME_KINDS = {"node", "python", "binary", "escript"}
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

# --- plugin_api 3: remote MCP grammar (M27 §7.2, §7.5, §7.6) -----------------
REMOTE_RUNTIME_KIND = "remote_mcp"
REMOTE_TRANSPORT = "streamable_http"
REMOTE_PROTOCOL_VERSION = "2025-06-18"
REMOTE_RUNTIME_FIELDS = {"kind", "transport", "protocol_version", "base_url", "mcp_path", "tool_name_mode"}
# A remote runtime has no host process: every local-process field is refused.
LOCAL_RUNTIME_FIELDS = {"command", "args", "env", "pass_env", "cwd", "vendored", "min_version"}
TOOL_NAME_MODES = {"prefix", "preserve"}

AUTH_VALIDATION_FIELDS = {"prefix", "min_bytes", "max_bytes", "charset", "forbid_whitespace"}
AUTH_VALIDATION_CHARSETS = {"visible_ascii"}
REMOTE_AUTH_HEADER = "authorization"
REMOTE_AUTH_SCHEME = "bearer"

CREDENTIAL_SCOPES = {"read", "write"}
SCOPE_VISIBILITIES = {"none", "all_scoped_tools_omitted"}
PROFILE_FIELDS = {"name", "display_name", "default", "required_credential_scope", "scope_visibility", "tools"}
RESOURCE_SCOPE_KINDS = {"single_workspace"}
RESOURCE_SCOPE_FIELDS = {"kind", "discovery_tool", "id_field", "label_field", "argument"}
RESULT_CONTRACT_KINDS = {"json_boolean"}
RESULT_CONTRACT_FIELDS = {"kind", "success_field", "status_field", "message_field"}
BUDGET_FIELDS = {"agent_turn_calls", "agent_turn_paginated_calls"}
REMOTE_POLICY_CLASSES = {"external_api"}
COLLECTION_POLICY_FIELDS = {
    "paginated",
    "request_limit_pointer",
    "default_limit",
    "result_items_pointer",
    "max_returned_items",
}
ARGUMENT_GUARD_FIELDS = {"pointer", "kind", "max_items"}
# Fixed core guards. A manifest picks the field and the maximum; it cannot
# weaken the guard, and it cannot introduce a new kind.
ARGUMENT_GUARD_KINDS = {"public_http_url_array", "bounded_visible_ascii_array"}
MAX_AGENT_TURN_CALLS = 100
MAX_COLLECTION_ITEMS = 100
MAX_ARGUMENT_GUARDS = 16
REMOTE_TOOL_REQUIRED_FIELDS = (
    "policy_class",
    "read_only",
    "replay_safe",
    "required_credential_scope",
    "rail",
    "parameters",
    "output_schema",
    "upstream_annotations",
    "descriptor_sha256",
)

# Fields admitted only by plugin_api >= 3. Under plugin_api 2 their mere
# presence is an error — they are never reinterpreted under v2 semantics.
API3_ONLY_ROOT_FIELDS = {"tool_profiles", "setup_tools", "resource_scope", "budgets", "result_contract"}
API3_ONLY_AUTH_FIELDS = {"validation"}
API3_ONLY_RUNTIME_FIELDS = {"transport", "protocol_version", "base_url", "mcp_path", "tool_name_mode"}
API3_ONLY_TOOL_FIELDS = {
    "replay_safe",
    "required_credential_scope",
    "collection_policy",
    "argument_guards",
    "output_schema",
    "upstream_annotations",
    "descriptor_sha256",
}

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
# A remote_mcp artifact is data only (M27 §9.1): manifest, docs, skills, assets.
# No src/, no bin/, no ecosystem file, no executable — there is nothing to run.
REMOTE_ALLOWED_TOP_LEVEL = {
    "plugin.json",
    "skills",
    "assets",
    "CHANGELOG.md",
    "README.md",
    "LICENSE",
    "yanked.json",
}

MIME_BY_EXT = {".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


class ValidationError(Exception):
    """A plugin failed validation; message lists every finding."""


class JcsError(ValueError):
    """A value cannot be canonicalized under RFC 8785 (JCS)."""


def load_manifest(plugin_dir: Path) -> dict:
    manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.is_file():
        raise ValidationError(f"{plugin_dir}: missing plugin.json at the plugin root")
    try:
        manifest = json_loads_strict(manifest_path.read_text())
    except json.JSONDecodeError as err:
        raise ValidationError(f"{manifest_path}: invalid JSON — {err}") from err
    except JcsError as err:
        raise ValidationError(f"{manifest_path}: invalid JSON — {err}") from err
    if not isinstance(manifest, dict):
        raise ValidationError(f"{manifest_path}: manifest must be a JSON object")
    return manifest


def plugin_api(manifest) -> int:
    """Declared plugin API level; 0 when absent or malformed (reported elsewhere)."""
    api = manifest.get("plugin_api")
    if isinstance(api, bool) or not isinstance(api, int):
        return 0
    return api


def is_remote_manifest(manifest) -> bool:
    """True for a validated-shape plugin-api-3 remote MCP manifest."""
    runtime = manifest.get("runtime")
    return (
        plugin_api(manifest) >= PLUGIN_API_REMOTE
        and isinstance(runtime, dict)
        and runtime.get("kind") == REMOTE_RUNTIME_KIND
    )


def validate_plugin_dir(plugin_dir: Path) -> dict:
    """Validate one plugin directory. Returns the manifest; raises ValidationError."""
    manifest = load_manifest(plugin_dir)
    remote = is_remote_manifest(manifest)
    errors = []
    errors += _validate_top_fields(manifest, plugin_dir)
    errors += _validate_api_gating(manifest)
    errors += _validate_auth(manifest)
    errors += _validate_tools(manifest, plugin_dir)
    errors += _validate_runtime(manifest)
    errors += _validate_remote_contract(manifest)
    errors += _validate_config(manifest)
    errors += _validate_skills(manifest, plugin_dir)
    errors += _validate_interface(manifest, plugin_dir)
    errors += check_boundary(
        [p.name for p in plugin_dir.iterdir()],
        has_runtime="runtime" in manifest,
        remote=remote,
    )
    errors += _check_no_symlinks(plugin_dir)
    if remote:
        errors += _check_remote_data_only(plugin_dir)
    if errors:
        raise ValidationError(f"{plugin_dir}:\n  - " + "\n  - ".join(errors))
    return manifest


def _check_no_symlinks(plugin_dir: Path):
    """Core's installer rejects symlink/hardlink archive members outright
    (traversal guard), so the publish side must too — otherwise a tree with
    links (e.g. npm's node_modules/.bin) gets signed and published only to
    fail at every user's install. Vendor with `npm ci --no-bin-links`."""
    links = [
        str(p.relative_to(plugin_dir))
        for p in sorted(plugin_dir.rglob("*"))
        if p.is_symlink()
    ]
    return [
        f"symlink {link!r}: links are rejected by the installer's archive guard"
        for link in links
    ]


def check_boundary(top_level_entries, has_runtime: bool, remote: bool = False):
    """Content-boundary allowlist over top-level entries (dir or archive).

    Anything not on the allowlist is rejected — including repo-level dotfiles
    like ``.git``, ``.github``, and ``.gitignore``. Core's installer rejects
    those at install time, so the publish side must reject them too; otherwise a
    mispacked archive could be signed and published only to fail at install.

    ``remote=True`` (a ``remote_mcp`` runtime) narrows the allowlist to the
    data-only set: the artifact has a runtime block but no host process, so
    ``src/``, ``bin/``, and the ecosystem files a local runtime implies are all
    refused (M27 §9.1).
    """
    if remote:
        allowed = REMOTE_ALLOWED_TOP_LEVEL
    else:
        allowed = ALLOWED_TOP_LEVEL | (RUNTIME_ECOSYSTEM_FILES if has_runtime else set())
    return [
        f"top-level entry {entry!r} violates the content-boundary allowlist "
        f"(allowed: {', '.join(sorted(allowed))})"
        for entry in sorted(set(top_level_entries))
        if entry not in allowed
    ]


def check_archive_listing(listing_lines, has_runtime: bool, remote: bool = False):
    """Boundary check over `tar -tzf` output: every member must sit under an
    allowed top-level entry, and plugin.json must be at the archive root.

    A listing carries names only, so the remote data-only rule is enforced here
    for nested ecosystem files; the executable-bit half of that rule needs the
    filesystem and lives in ``_check_remote_data_only``.
    """
    top = set()
    members = []
    saw_manifest = False
    for raw in listing_lines:
        member = raw.strip().lstrip("./")
        if not member:
            continue
        members.append(member)
        head = member.split("/", 1)[0]
        top.add(head)
        if member == "plugin.json":
            saw_manifest = True
    errors = check_boundary(top, has_runtime, remote=remote)
    if remote:
        errors += [
            f"archive member {member!r}: a remote_mcp artifact carries no dependency "
            f"ecosystem file (it runs no local process)"
            for member in sorted(set(members))
            if member.rstrip("/").split("/")[-1] in RUNTIME_ECOSYSTEM_FILES
        ]
    if not saw_manifest:
        errors.append("plugin.json is not at the archive root (pack with `tar -C plugins/<name> … .`)")
    return errors


def _check_remote_data_only(plugin_dir: Path):
    """Filesystem half of the remote data-only rule: no ecosystem file anywhere
    and no executable file anywhere (the mode bit, not just the name)."""
    errors = []
    for path in sorted(plugin_dir.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(plugin_dir).as_posix()
        if path.name in RUNTIME_ECOSYSTEM_FILES:
            errors.append(
                f"{rel}: a remote_mcp artifact carries no dependency ecosystem file "
                f"(it runs no local process)"
            )
        if path.stat().st_mode & 0o111:
            mode = path.stat().st_mode & 0o777
            errors.append(
                f"{rel}: a remote_mcp artifact must contain no executable file (mode {mode:03o})"
            )
    return errors


def _validate_top_fields(manifest, plugin_dir):
    errors = []
    version = manifest.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version != SCHEMA_VERSION:
        # M8 §5.2: an unknown major is REFUSED, never parsed as the newest known
        # one. A future schema_version 3 gets its own decoder, not v2 semantics.
        errors.append(
            f"schema_version must be exactly {SCHEMA_VERSION} for distributed plugins "
            f"(got {version!r}; an unknown schema major is refused, "
            f"not parsed as {SCHEMA_VERSION})"
        )
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


def _validate_api_gating(manifest):
    """plugin_api 3 is additive and version-conditional (M27 §7.1).

    Under plugin_api 2 the presence of any plugin-api-3-only field is an error:
    the field is refused, never accepted under v2 semantics.
    """
    api = manifest.get("plugin_api")
    if isinstance(api, bool) or not isinstance(api, int):
        return []  # _validate_top_fields already reported the malformed value
    if api >= PLUGIN_API_REMOTE:
        return []
    errors = [
        f"{field} requires plugin_api >= {PLUGIN_API_REMOTE} (manifest declares plugin_api {api})"
        for field in sorted(API3_ONLY_ROOT_FIELDS & set(manifest))
    ]
    auth = manifest.get("auth")
    if isinstance(auth, dict):
        errors += [
            f"auth.{field} requires plugin_api >= {PLUGIN_API_REMOTE} (manifest declares plugin_api {api})"
            for field in sorted(API3_ONLY_AUTH_FIELDS & set(auth))
        ]
    runtime = manifest.get("runtime")
    if isinstance(runtime, dict):
        errors += [
            f"runtime.{field} requires plugin_api >= {PLUGIN_API_REMOTE} (manifest declares plugin_api {api})"
            for field in sorted(API3_ONLY_RUNTIME_FIELDS & set(runtime))
        ]
        if runtime.get("kind") == REMOTE_RUNTIME_KIND:
            errors.append(
                f"runtime.kind {REMOTE_RUNTIME_KIND!r} requires plugin_api >= {PLUGIN_API_REMOTE} "
                f"(manifest declares plugin_api {api})"
            )
    errors += _api_gating_tool_errors(manifest.get("tools"), api)
    return errors


def _api_gating_tool_errors(tools, api):
    if not isinstance(tools, list):
        return []
    errors = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        label = tool.get("name") if isinstance(tool.get("name"), str) else "<unnamed tool>"
        errors += [
            f"{label}: {field} requires plugin_api >= {PLUGIN_API_REMOTE} "
            f"(manifest declares plugin_api {api})"
            for field in sorted(API3_ONLY_TOOL_FIELDS & set(tool))
        ]
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
        # An empty list is valid: some providers (Notion) have no scope model.
        scopes = auth.get("scopes")
        if not isinstance(scopes, list) or not all(isinstance(s, str) and s for s in scopes):
            errors.append("oauth2 plugins must declare auth.scopes as a list of non-empty strings")
        if not isinstance(manifest.get("health_check"), dict):
            errors.append("oauth2 plugins must declare a health_check")
    if auth_type == "api_key":
        for field in ("key_name", "header", "prompt"):
            if not isinstance(auth.get(field), str) or not auth[field].strip():
                errors.append(f"api_key plugins must declare auth.{field}")
    if plugin_api(manifest) >= PLUGIN_API_REMOTE and "validation" in auth:
        errors += _validate_auth_validation(auth.get("validation"))
    if is_remote_manifest(manifest):
        errors += _validate_remote_auth(auth)
    return errors


def _validate_remote_auth(auth):
    """Remote-MCP v1 accepts exactly one auth shape (M27 §7.2 rule 8): an
    api_key sent as `Authorization: Bearer <credential>`. Header names and auth
    schemes are case-insensitive on the wire, so both match case-insensitively;
    no arbitrary header is ever accepted from a manifest."""
    errors = []
    if auth.get("type") != "api_key":
        errors.append(f"remote_mcp v1 requires auth.type 'api_key' (got {auth.get('type')!r})")
    header = auth.get("header")
    if not isinstance(header, str) or header.strip().lower() != REMOTE_AUTH_HEADER:
        errors.append(
            f"remote_mcp v1 requires auth.header 'Authorization' (case-insensitive; got {header!r})"
        )
    scheme = auth.get("scheme")
    if not isinstance(scheme, str) or scheme.strip().lower() != REMOTE_AUTH_SCHEME:
        errors.append(f"remote_mcp v1 requires auth.scheme 'Bearer' (case-insensitive; got {scheme!r})")
    return errors


def _validate_auth_validation(validation):
    """auth.validation is a BOUNDED DECLARATIVE block (M27 §7.5): a literal
    prefix, byte bounds, a fixed charset enum, and a whitespace prohibition.
    No regex, no executable validator, no other key."""
    if not isinstance(validation, dict):
        return ["auth.validation must be an object"]
    errors = [
        f"auth.validation has unknown key {key!r} (allowed: {', '.join(sorted(AUTH_VALIDATION_FIELDS))}; "
        f"no regex or executable validator is accepted)"
        for key in sorted(set(validation) - AUTH_VALIDATION_FIELDS)
    ]
    if "prefix" in validation:
        errors += _validate_auth_prefix(validation["prefix"])
    bounds = {}
    for field in ("min_bytes", "max_bytes"):
        if field not in validation:
            continue
        value = validation[field]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            errors.append(f"auth.validation.{field} must be a positive integer")
        else:
            bounds[field] = value
    if len(bounds) == 2 and bounds["min_bytes"] > bounds["max_bytes"]:
        errors.append("auth.validation.min_bytes must not exceed auth.validation.max_bytes")
    if "charset" in validation and validation["charset"] not in AUTH_VALIDATION_CHARSETS:
        errors.append(f"auth.validation.charset must be one of {sorted(AUTH_VALIDATION_CHARSETS)}")
    if "forbid_whitespace" in validation and not isinstance(validation["forbid_whitespace"], bool):
        errors.append("auth.validation.forbid_whitespace must be a boolean")
    return errors


def _validate_auth_prefix(prefix):
    if not isinstance(prefix, str) or not prefix:
        return ["auth.validation.prefix must be a non-empty literal string"]
    if any(ch in REGEX_METACHARS for ch in prefix):
        return [
            "auth.validation.prefix must be a literal string, not a pattern "
            f"(found regex metacharacter in {prefix!r})"
        ]
    if any(ch.isspace() or not (0x21 <= ord(ch) <= 0x7E) for ch in prefix):
        return ["auth.validation.prefix must be visible ASCII with no whitespace"]
    return []


def _validate_tools(manifest, plugin_dir):
    tools = manifest.get("tools")
    if tools is None or (isinstance(tools, list) and not tools):
        # A native-binary plugin (ships a signed bin/<target>/ tree, spawned by
        # core's PortDriver, exposing no agent tools) legitimately declares no
        # tools. It is identified by a maintainer-authored native-builds/<name>.json
        # build descriptor at the repo root; every other plugin must declare >= 1.
        name = manifest.get("name") or ""
        descriptor = plugin_dir.parent.parent / "native-builds" / f"{name}.json"
        if descriptor.is_file():
            return []
        return ["tools must be a non-empty list"]
    if not isinstance(tools, list):
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
        declared = auth.get("scopes") or []
        scopes = tool.get("requires_scopes")
        if not declared:
            # Scope-less provider: tools must not require scopes.
            if scopes:
                errors.append(f"{label}: requires_scopes must be a subset of auth.scopes")
        elif not isinstance(scopes, list) or not scopes:
            errors.append(f"{label}: oauth2 tools must declare requires_scopes")
        elif not set(scopes) <= set(declared):
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
    if not isinstance(runtime, dict):
        return ["runtime must be an object"]
    if runtime.get("kind") == REMOTE_RUNTIME_KIND:
        return _validate_remote_runtime(manifest, runtime, needs_runtime)
    errors = []
    if not needs_runtime:
        errors.append("runtime block declared but no tool has rail: mcp")
    if runtime.get("kind") not in RUNTIME_KINDS:
        errors.append(f"runtime.kind must be one of {sorted(RUNTIME_KINDS)}")
    # M8 §8 shape: `command` is one executable name (a space-joined
    # "node src/index.js" would pass publish and fail at spawn — the stdio
    # transport resolves `command` whole); `args` is a separate list.
    command = runtime.get("command")
    if not isinstance(command, str) or not command:
        errors.append("runtime.command is required")
    elif any(ch.isspace() for ch in command):
        errors.append("runtime.command must be a single executable name (no whitespace)")
    elif "/" in command or command in ("..", "."):
        # A vendored command resolves under bin/<target>/; `/` or `..` would let
        # it escape to a host executable like /bin/sh. Mirror the core decoder.
        errors.append("runtime.command must be a bare executable name (no '/' or '..')")
    args = runtime.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) and a for a in args):
        errors.append("runtime.args must be a list of non-empty strings")
    if not isinstance(runtime.get("vendored"), bool):
        errors.append("runtime.vendored must be a boolean")
    if "tool_name_mode" in runtime and runtime["tool_name_mode"] != "prefix":
        # `preserve` is admissible only for a plugin-api-3 remote plugin
        # (M27 §7.2 rule 9); a local MCP server's tools are always prefixed.
        errors.append(
            "runtime.tool_name_mode must be 'prefix' for a local runtime "
            f"('preserve' is {REMOTE_RUNTIME_KIND} only)"
        )
    return errors


def _validate_remote_runtime(manifest, runtime, needs_runtime):
    """`runtime.kind: remote_mcp` (M27 §7.2).

    The mcp-rail requirement inverts here: every tool still rides the mcp rail,
    but there is no host executable to probe, so `command`/`args`/`env`/
    `pass_env`/`cwd`/`vendored`/`min_version` are all refused. The endpoint is
    signed manifest data — user config and environment cannot override it.
    """
    errors = [
        f"runtime.{field} is not allowed with runtime.kind {REMOTE_RUNTIME_KIND!r} "
        f"(a remote runtime spawns no local process)"
        for field in sorted(LOCAL_RUNTIME_FIELDS & set(runtime))
    ]
    errors += [
        f"runtime has unknown key {key!r} for kind {REMOTE_RUNTIME_KIND!r} "
        f"(allowed: {', '.join(sorted(REMOTE_RUNTIME_FIELDS))})"
        for key in sorted(set(runtime) - REMOTE_RUNTIME_FIELDS - LOCAL_RUNTIME_FIELDS)
    ]
    if not needs_runtime:
        errors.append("runtime block declared but no tool has rail: mcp")
    if runtime.get("transport") != REMOTE_TRANSPORT:
        errors.append(f"runtime.transport must be exactly {REMOTE_TRANSPORT!r}")
    if runtime.get("protocol_version") != REMOTE_PROTOCOL_VERSION:
        errors.append(f"runtime.protocol_version must be exactly {REMOTE_PROTOCOL_VERSION!r}")
    errors += _validate_base_url(runtime.get("base_url"))
    errors += _validate_mcp_path(runtime.get("mcp_path"))
    errors += _validate_tool_name_mode(manifest, runtime.get("tool_name_mode"))
    return errors


def _validate_tool_name_mode(manifest, mode):
    """`preserve` keeps the upstream tool name verbatim, so it is admissible
    only when every declared name is already namespaced `<plugin>_…` — otherwise
    a remote server could claim any capability name (M27 §7.2 rule 9, §7.7)."""
    if mode not in TOOL_NAME_MODES:
        return [f"runtime.tool_name_mode must be one of {sorted(TOOL_NAME_MODES)}"]
    if mode != "preserve":
        return []
    name = manifest.get("name") if isinstance(manifest.get("name"), str) else ""
    tools = manifest.get("tools") if isinstance(manifest.get("tools"), list) else []
    unnamespaced = sorted(
        tool.get("name")
        for tool in tools
        if isinstance(tool, dict)
        and isinstance(tool.get("name"), str)
        and not tool["name"].startswith(f"{name}_")
    )
    if not unnamespaced:
        return []
    return [
        f"runtime.tool_name_mode 'preserve' requires every declared tool to start with "
        f"{name + '_'!r}; offending: {', '.join(repr(t) for t in unnamespaced)}"
    ]


def _validate_base_url(base_url):
    """HTTPS ORIGIN only: scheme + host (+ optional port). No userinfo, path,
    query, fragment, template, wildcard, or IP literal (M27 §7.2 rule 4)."""
    if not isinstance(base_url, str) or not base_url:
        return ["runtime.base_url is required"]
    if not base_url.startswith("https://"):
        return [f"runtime.base_url must use the https:// scheme (got {base_url!r})"]
    authority = base_url[len("https://"):]
    for char, why in (("{", "template"), ("}", "template"), ("*", "wildcard"), ("@", "userinfo")):
        if char in authority:
            return [f"runtime.base_url must not contain {char!r} ({why} is refused): {base_url!r}"]
    for char, why in (("/", "path"), ("?", "query"), ("#", "fragment")):
        if char in authority:
            return [f"runtime.base_url must be an origin with no {why} (found {char!r}): {base_url!r}"]
    return _validate_origin_authority(authority, base_url)


def _validate_origin_authority(authority, base_url):
    host = authority
    if ":" in authority and "[" not in authority:
        host, _, port = authority.rpartition(":")
        if not port.isdigit() or port != str(int(port)) or not 1 <= int(port) <= 65535:
            return [f"runtime.base_url port must be a decimal 1-65535: {base_url!r}"]
    if not host:
        return [f"runtime.base_url must have a non-empty host: {base_url!r}"]
    if "[" in authority or "]" in authority or authority.count(":") > 1:
        return [f"runtime.base_url must name a host, not an IP literal: {base_url!r}"]
    if not HOSTNAME_RE.match(host) or len(host.encode()) > MAX_HOSTNAME_BYTES:
        return [f"runtime.base_url host must be a literal DNS hostname: {base_url!r}"]
    if _is_ip_literal(host):
        return [f"runtime.base_url must name a host, not an IP literal: {base_url!r}"]
    return []


def _is_ip_literal(host):
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        # RFC 1123: a real TLD is never all-digits, so "1.2.3.4.5" is an
        # address-shaped host, not a hostname.
        return host.split(".")[-1].isdigit()


def _validate_mcp_path(mcp_path):
    """A literal absolute path (M27 §7.2 rule 5): no query, fragment, backslash,
    dot segment, percent-encoded slash, template, or empty segment."""
    if not isinstance(mcp_path, str) or not mcp_path:
        return ["runtime.mcp_path is required"]
    if not mcp_path.startswith("/"):
        return [f"runtime.mcp_path must be an absolute path starting with '/': {mcp_path!r}"]
    forbidden = (("?", "query"), ("#", "fragment"), ("\\", "backslash"), ("{", "template"), ("}", "template"))
    for char, why in forbidden:
        if char in mcp_path:
            return [f"runtime.mcp_path must not contain {char!r} ({why} is refused): {mcp_path!r}"]
    if "%2f" in mcp_path.lower():
        return [f"runtime.mcp_path must not contain a percent-encoded slash: {mcp_path!r}"]
    if any(not 0x21 <= ord(ch) <= 0x7E for ch in mcp_path):
        return [f"runtime.mcp_path must be visible ASCII with no whitespace: {mcp_path!r}"]
    segments = mcp_path[1:].split("/")
    if any(segment == "" for segment in segments):
        return [f"runtime.mcp_path must have no empty segment: {mcp_path!r}"]
    if any(segment in (".", "..") for segment in segments):
        return [f"runtime.mcp_path must have no '.' or '..' segment: {mcp_path!r}"]
    return []


# --- plugin_api 3 remote contract: profiles, scope, budgets, signed tools ----


def _bounded_int(value, maximum, minimum=1):
    """True for a plain integer within [minimum, maximum] — booleans are not ints here."""
    return not isinstance(value, bool) and isinstance(value, int) and minimum <= value <= maximum


def _validate_remote_contract(manifest):
    """The plugin-api-3 declarative interaction policy (M27 §7.6, §9.2).

    Blocks are validated whenever plugin_api >= 3 declares them and REQUIRED for
    a remote_mcp runtime, whose `tools` list is an enforcement boundary rather
    than a preview.
    """
    if plugin_api(manifest) < PLUGIN_API_REMOTE:
        return []
    remote = is_remote_manifest(manifest)
    tools = _tools_by_name(manifest)
    setup_tools = _setup_tool_names(manifest)
    errors = []
    errors += _validate_tool_profiles(manifest, tools, setup_tools, remote)
    errors += _validate_setup_tools(manifest, tools)
    errors += _validate_resource_scope(manifest, tools, setup_tools)
    errors += _validate_budgets(manifest, remote)
    errors += _validate_result_contract(manifest, remote)
    if remote:
        errors += _validate_remote_tools(manifest)
    return errors


def _tools_by_name(manifest):
    tools = manifest.get("tools")
    if not isinstance(tools, list):
        return {}
    return {
        tool["name"]: tool
        for tool in tools
        if isinstance(tool, dict) and isinstance(tool.get("name"), str)
    }


def _setup_tool_names(manifest):
    setup = manifest.get("setup_tools")
    if not isinstance(setup, list):
        return set()
    return {name for name in setup if isinstance(name, str)}


def _profile_tool_names(manifest):
    profiles = manifest.get("tool_profiles")
    if not isinstance(profiles, list):
        return []
    names = []
    for profile in profiles:
        if not isinstance(profile, dict) or not isinstance(profile.get("tools"), list):
            continue
        names += [name for name in profile["tools"] if isinstance(name, str)]
    return names


def _validate_tool_profiles(manifest, tools, setup_tools, required):
    profiles = manifest.get("tool_profiles")
    if profiles is None:
        return ["tool_profiles is required for a remote_mcp plugin"] if required else []
    if not isinstance(profiles, list) or not profiles:
        return ["tool_profiles must be a non-empty list"]
    errors = []
    seen = set()
    defaults = 0
    for profile in profiles:
        if not isinstance(profile, dict):
            errors.append("each tool_profiles entry must be an object")
            continue
        if profile.get("default") is True:
            defaults += 1
        errors += _validate_profile(profile, tools, setup_tools, seen)
    if defaults != 1:
        errors.append(f"exactly one tool_profiles entry must set default: true (found {defaults})")
    return errors


def _validate_profile(profile, tools, setup_tools, seen):
    name = profile.get("name")
    label = f"tool_profile {name!r}" if isinstance(name, str) and name else "<unnamed tool_profile>"
    errors = [
        f"{label}: unknown field {field!r} (allowed: {', '.join(sorted(PROFILE_FIELDS))})"
        for field in sorted(set(profile) - PROFILE_FIELDS)
    ]
    if not isinstance(name, str) or not PROFILE_NAME_RE.match(name):
        errors.append(f"{label}: name must match {PROFILE_NAME_RE.pattern}")
    elif name in seen:
        errors.append(f"{label}: duplicate profile name")
    else:
        seen.add(name)
    if not isinstance(profile.get("display_name"), str) or not profile["display_name"].strip():
        errors.append(f"{label}: display_name must be a non-empty string")
    if not isinstance(profile.get("default"), bool):
        errors.append(f"{label}: default must be a boolean")
    if profile.get("required_credential_scope") not in CREDENTIAL_SCOPES:
        errors.append(f"{label}: required_credential_scope must be one of {sorted(CREDENTIAL_SCOPES)}")
    if profile.get("scope_visibility") not in SCOPE_VISIBILITIES:
        errors.append(f"{label}: scope_visibility must be one of {sorted(SCOPE_VISIBILITIES)}")
    errors += _validate_profile_tools(profile.get("tools"), label, tools, setup_tools)
    return errors


def _validate_profile_tools(names, label, tools, setup_tools):
    if not isinstance(names, list) or not names:
        return [f"{label}: tools must be a non-empty list of declared tool names"]
    errors = []
    seen = set()
    for name in names:
        if not isinstance(name, str) or name not in tools:
            errors.append(f"{label}: tool {name!r} is not declared in tools")
            continue
        if name in seen:
            errors.append(f"{label}: duplicate tool {name!r}")
        seen.add(name)
        if name in setup_tools:
            errors.append(f"{label}: tool {name!r} is a setup_tools member and must not appear in a profile")
    return errors


def _validate_setup_tools(manifest, tools):
    setup = manifest.get("setup_tools")
    if setup is None:
        return []
    if not isinstance(setup, list):
        return ["setup_tools must be a list of declared tool names"]
    errors = []
    seen = set()
    for name in setup:
        if not isinstance(name, str) or name not in tools:
            errors.append(f"setup_tools: tool {name!r} is not declared in tools")
            continue
        if name in seen:
            errors.append(f"setup_tools: duplicate tool {name!r}")
        seen.add(name)
    return errors


def _validate_resource_scope(manifest, tools, setup_tools):
    scope = manifest.get("resource_scope")
    if scope is None:
        return []
    if not isinstance(scope, dict):
        return ["resource_scope must be an object"]
    errors = [
        f"resource_scope: unknown field {field!r} (allowed: {', '.join(sorted(RESOURCE_SCOPE_FIELDS))})"
        for field in sorted(set(scope) - RESOURCE_SCOPE_FIELDS)
    ]
    if scope.get("kind") not in RESOURCE_SCOPE_KINDS:
        errors.append(f"resource_scope.kind must be one of {sorted(RESOURCE_SCOPE_KINDS)}")
    discovery = scope.get("discovery_tool")
    if not isinstance(discovery, str) or discovery not in tools:
        errors.append(f"resource_scope.discovery_tool {discovery!r} is not declared in tools")
    elif discovery not in setup_tools:
        errors.append(f"resource_scope.discovery_tool {discovery!r} must be a setup_tools member")
    for field in ("id_field", "label_field", "argument"):
        if not isinstance(scope.get(field), str) or not scope[field].strip():
            errors.append(f"resource_scope.{field} must be a non-empty string")
    if isinstance(scope.get("argument"), str) and scope["argument"].strip():
        errors += _validate_scope_argument(manifest, tools, scope["argument"])
    return errors


def _validate_scope_argument(manifest, tools, argument):
    """The scope argument is the field core strips from the exposed schema and
    injects at call time, so every profile tool must actually accept it."""
    errors = []
    for name in sorted(set(_profile_tool_names(manifest))):
        tool = tools.get(name)
        if tool is None:
            continue  # already reported as undeclared
        parameters = tool.get("parameters")
        properties = parameters.get("properties") if isinstance(parameters, dict) else None
        if not isinstance(properties, dict) or argument not in properties:
            errors.append(
                f"{name}: parameters.properties must declare the resource_scope argument {argument!r}"
            )
    return errors


def _validate_budgets(manifest, required):
    budgets = manifest.get("budgets")
    if budgets is None:
        return ["budgets is required for a remote_mcp plugin"] if required else []
    if not isinstance(budgets, dict):
        return ["budgets must be an object"]
    errors = [
        f"budgets: unknown field {field!r} (allowed: {', '.join(sorted(BUDGET_FIELDS))})"
        for field in sorted(set(budgets) - BUDGET_FIELDS)
    ]
    values = {}
    for field in ("agent_turn_calls", "agent_turn_paginated_calls"):
        value = budgets.get(field)
        if not _bounded_int(value, MAX_AGENT_TURN_CALLS):
            errors.append(f"budgets.{field} must be an integer 1..{MAX_AGENT_TURN_CALLS}")
        else:
            values[field] = value
    if len(values) == 2 and values["agent_turn_paginated_calls"] > values["agent_turn_calls"]:
        errors.append("budgets.agent_turn_paginated_calls must not exceed budgets.agent_turn_calls")
    return errors


def _validate_result_contract(manifest, required):
    contract = manifest.get("result_contract")
    if contract is None:
        return ["result_contract is required for a remote_mcp plugin"] if required else []
    if not isinstance(contract, dict):
        return ["result_contract must be an object"]
    errors = [
        f"result_contract: unknown field {field!r} (allowed: {', '.join(sorted(RESULT_CONTRACT_FIELDS))})"
        for field in sorted(set(contract) - RESULT_CONTRACT_FIELDS)
    ]
    if contract.get("kind") not in RESULT_CONTRACT_KINDS:
        errors.append(f"result_contract.kind must be one of {sorted(RESULT_CONTRACT_KINDS)}")
    for field in ("success_field", "status_field", "message_field"):
        if not isinstance(contract.get(field), str) or not contract[field].strip():
            errors.append(f"result_contract.{field} must be a non-empty string")
    return errors


def _validate_remote_tools(manifest):
    tools = manifest.get("tools")
    if not isinstance(tools, list):
        return []
    errors = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue  # already reported by _validate_tools
        name = tool.get("name")
        errors += _validate_remote_tool(tool, name if isinstance(name, str) and name else "<unnamed tool>")
    return errors


def _validate_remote_tool(tool, label):
    errors = [
        f"{label}: {field} is required for a remote_mcp tool"
        for field in REMOTE_TOOL_REQUIRED_FIELDS
        if field not in tool
    ]
    if "policy_class" in tool and tool["policy_class"] not in REMOTE_POLICY_CLASSES:
        errors.append(f"{label}: policy_class must be one of {sorted(REMOTE_POLICY_CLASSES)}")
    if "replay_safe" in tool and not isinstance(tool["replay_safe"], bool):
        errors.append(f"{label}: replay_safe must be a boolean (signed independently of read_only)")
    if "required_credential_scope" in tool and tool["required_credential_scope"] not in CREDENTIAL_SCOPES:
        errors.append(f"{label}: required_credential_scope must be one of {sorted(CREDENTIAL_SCOPES)}")
    if tool.get("rail") != "mcp":
        errors.append(f"{label}: rail must be 'mcp' for a remote_mcp plugin")
    parameters = tool.get("parameters")
    if not isinstance(parameters, dict) or parameters.get("type") != "object":
        errors.append(f"{label}: parameters must be an object schema (type: object)")
    for field in ("output_schema", "upstream_annotations"):
        if field in tool and tool[field] is not None and not isinstance(tool[field], dict):
            errors.append(f"{label}: {field} must be an object or null")
    errors += _validate_descriptor_hash(tool, label)
    errors += _validate_collection_policy(tool, label)
    errors += _validate_argument_guards(tool, label)
    return errors


def _validate_descriptor_hash(tool, label):
    """Recompute the canonical security descriptor locally (M27 §7.6 rule 6):
    SHA-256 over RFC 8785 JCS of {name, inputSchema, outputSchema, annotations}."""
    declared = tool.get("descriptor_sha256")
    if not isinstance(declared, str) or not SHA256_HEX_RE.match(declared):
        return [f"{label}: descriptor_sha256 must be 64 lowercase hex characters"]
    parts = (
        tool.get("name"),
        tool.get("parameters"),
        tool.get("output_schema"),
        tool.get("upstream_annotations"),
    )
    if not isinstance(parts[0], str) or not isinstance(parts[1], dict):
        return []  # shape already reported; hashing an invalid descriptor is meaningless
    try:
        actual = descriptor_sha256(*parts)
    except JcsError as err:
        return [f"{label}: descriptor cannot be canonicalized — {err}"]
    if actual != declared:
        return [
            f"{label}: descriptor_sha256 {declared} does not match the canonical descriptor "
            f"of name/inputSchema/outputSchema/annotations ({actual})"
        ]
    return []


def _validate_collection_policy(tool, label):
    policy = tool.get("collection_policy")
    if policy is None:
        return []
    if not isinstance(policy, dict):
        return [f"{label}: collection_policy must be an object or null"]
    errors = [
        f"{label}: collection_policy has unknown key {key!r} "
        f"(allowed: {', '.join(sorted(COLLECTION_POLICY_FIELDS))})"
        for key in sorted(set(policy) - COLLECTION_POLICY_FIELDS)
    ]
    errors += [
        f"{label}: collection_policy.{field} is required"
        for field in sorted(COLLECTION_POLICY_FIELDS - set(policy))
    ]
    if "paginated" in policy and policy["paginated"] is not True:
        errors.append(f"{label}: collection_policy.paginated must be true (omit the block otherwise)")
    for field in ("default_limit", "max_returned_items"):
        if field in policy and not _bounded_int(policy[field], MAX_COLLECTION_ITEMS):
            errors.append(f"{label}: collection_policy.{field} must be an integer 1..{MAX_COLLECTION_ITEMS}")
    errors += _check_pointer(
        policy.get("request_limit_pointer"), tool.get("parameters"), ("integer", "number"),
        f"{label}: collection_policy.request_limit_pointer", "parameters",
    )
    # `result_items_pointer` names where the returned collection lives in the
    # tool RESULT, and the call proxy caps that collection at runtime either
    # way. The signed output schema is a cross-check, not the enforcement — and
    # Stage 0 against Eden found it is usually absent (all 78 of its tools
    # publish `outputSchema: null`, which is common for MCP servers). Requiring
    # one would make collection_policy unusable against real servers, so the
    # schema check applies when a schema is published and the pointer is
    # syntax-checked when it is not. Mirror of the core decoder.
    if tool.get("output_schema") is None:
        errors += _check_pointer_syntax(
            policy.get("result_items_pointer"),
            f"{label}: collection_policy.result_items_pointer",
        )
    else:
        errors += _check_pointer(
            policy.get("result_items_pointer"), tool.get("output_schema"), ("array",),
            f"{label}: collection_policy.result_items_pointer", "output_schema",
        )
    return errors


def _check_pointer_syntax(pointer, label):
    """RFC 6901 shape only — used when there is no schema to resolve against."""
    if not isinstance(pointer, str) or not pointer:
        return [f"{label} must be a non-empty RFC 6901 pointer"]
    if "*" in pointer:
        return [f"{label} must not contain a wildcard"]
    if not pointer.startswith("/"):
        return [f"{label} must start with '/'"]
    for seg in pointer.split("/")[1:]:
        if seg == "":
            return [f"{label} must not contain an empty segment"]
        if "~" in seg.replace("~0", "").replace("~1", ""):
            return [f"{label} has an invalid '~' escape"]
    return []


def _validate_argument_guards(tool, label):
    guards = tool.get("argument_guards")
    if guards is None and "argument_guards" not in tool:
        return []
    if not isinstance(guards, list):
        return [f"{label}: argument_guards must be a list"]
    if len(guards) > MAX_ARGUMENT_GUARDS:
        return [f"{label}: argument_guards may declare at most {MAX_ARGUMENT_GUARDS} guards"]
    errors = []
    for guard in guards:
        if not isinstance(guard, dict):
            errors.append(f"{label}: each argument_guards entry must be an object")
            continue
        errors += _validate_argument_guard(guard, tool, label)
    return errors


def _validate_argument_guard(guard, tool, label):
    errors = [
        f"{label}: argument_guards entry has unknown key {key!r} "
        f"(allowed: {', '.join(sorted(ARGUMENT_GUARD_FIELDS))})"
        for key in sorted(set(guard) - ARGUMENT_GUARD_FIELDS)
    ]
    if guard.get("kind") not in ARGUMENT_GUARD_KINDS:
        errors.append(
            f"{label}: argument_guards kind must be one of {sorted(ARGUMENT_GUARD_KINDS)} "
            f"(the guards are fixed in core; a manifest picks the field and maximum only)"
        )
    if not _bounded_int(guard.get("max_items"), MAX_COLLECTION_ITEMS):
        errors.append(f"{label}: argument_guards max_items must be an integer 1..{MAX_COLLECTION_ITEMS}")
    errors += _check_pointer(
        guard.get("pointer"), tool.get("parameters"), ("array",),
        f"{label}: argument_guards pointer", "parameters",
    )
    return errors


def _check_pointer(pointer, schema, expected_types, prefix, schema_label):
    """RFC 6901 pointer, no wildcards, resolving to a compatible signed location."""
    try:
        tokens = _parse_pointer(pointer)
    except ValueError as err:
        return [f"{prefix} {pointer!r} {err}"]
    if not isinstance(schema, dict):
        return [f"{prefix} {pointer!r} cannot resolve: {schema_label} is not an object schema"]
    target = _resolve_schema_pointer(schema, tokens)
    if not isinstance(target, dict):
        return [f"{prefix} {pointer!r} does not resolve in the signed {schema_label}"]
    if target.get("type") not in expected_types:
        return [
            f"{prefix} {pointer!r} resolves to type {target.get('type')!r} in {schema_label}; "
            f"expected one of {sorted(expected_types)}"
        ]
    return []


def _parse_pointer(pointer):
    """RFC 6901 → reference tokens. Raises ValueError with the reason."""
    if not isinstance(pointer, str) or not pointer:
        raise ValueError("must be a non-empty RFC 6901 JSON pointer")
    if not pointer.startswith("/"):
        raise ValueError("must be an RFC 6901 JSON pointer starting with '/'")
    if "*" in pointer:
        raise ValueError("must not contain a wildcard")
    tokens = []
    for raw in pointer[1:].split("/"):
        if not raw:
            raise ValueError("must not contain an empty reference token")
        if re.search(r"~(?![01])", raw):
            raise ValueError("has an invalid '~' escape (use ~0 and ~1)")
        tokens.append(raw.replace("~1", "/").replace("~0", "~"))
    return tokens


def _resolve_schema_pointer(schema, tokens):
    """Walk a JSON-Schema object by property name; None when unresolvable."""
    node = schema
    for token in tokens:
        properties = node.get("properties") if isinstance(node, dict) else None
        if not isinstance(properties, dict) or token not in properties:
            return None
        node = properties[token]
    return node


CONFIG_ENTRY_FIELDS = {"key", "prompt", "required"}


def _validate_config(manifest):
    """Per-plugin config declarations (M8.1 §4.4) — mirrors the core decoder:
    flat key/prompt/required entries, UPPER_SNAKE keys, nothing more."""
    config = manifest.get("config")
    if config is None:
        return []
    if not isinstance(config, list):
        return ["config must be a list of {key, prompt, required} entries"]
    errors = []
    seen = set()
    for entry in config:
        if not isinstance(entry, dict):
            errors.append("each config entry must be an object")
            continue
        errors += _validate_config_entry(entry, seen)
    return errors


def _validate_config_entry(entry, seen):
    errors = []
    key = entry.get("key")
    label = key if isinstance(key, str) and key else "<unnamed config entry>"
    unknown = sorted(set(entry) - CONFIG_ENTRY_FIELDS)
    if unknown:
        errors.append(f"{label}: config entry has unknown fields: {', '.join(unknown)}")
    if not isinstance(key, str) or not CONFIG_KEY_RE.match(key):
        errors.append(f"{label}: config key must match ^[A-Z][A-Z0-9_]*$")
    elif key in seen:
        errors.append(f"{label}: duplicate config key")
    else:
        seen.add(key)
    prompt = entry.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append(f"{label}: config prompt must be a non-empty string")
    if not isinstance(entry.get("required", False), bool):
        errors.append(f"{label}: config required must be a boolean")
    return errors


def _path_within(plugin_dir, rel):
    """True iff the manifest-relative path `rel` resolves inside `plugin_dir`.

    Rejects absolute paths and `..` escapes so a manifest can't point skills or
    interface assets at sibling plugins or repo files — the same content boundary
    the Fermix installer enforces at install time.
    """
    if not isinstance(rel, str) or not rel:
        return False
    base = plugin_dir.resolve()
    try:
        (plugin_dir / rel).resolve().relative_to(base)
    except (ValueError, OSError):
        return False
    return True


def _validate_skills(manifest, plugin_dir):
    errors = []
    for skill in manifest.get("skills") or []:
        if not isinstance(skill, dict) or not skill.get("name") or not skill.get("path"):
            errors.append("each skill needs name and path")
            continue
        if skill["name"] == manifest.get("name"):
            errors.append(f"skill {skill['name']!r} must not equal the plugin name")
        if not _path_within(plugin_dir, skill["path"]):
            errors.append(f"skill path {skill['path']!r} must stay inside the plugin directory")
        elif not (plugin_dir / skill["path"]).is_file():
            errors.append(f"skill path {skill['path']!r} does not exist")
    return errors


def _validate_interface(manifest, plugin_dir):
    errors = []
    interface = manifest.get("interface") or {}
    for field in ("icon", "logo"):
        rel = interface.get(field)
        if rel is None:
            continue
        if not _path_within(plugin_dir, rel):
            errors.append(f"interface.{field} {rel!r} must stay inside the plugin directory")
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


# --- RFC 8785 JSON Canonicalization Scheme (cross-language contract) ---------
#
# Fermix core computes the same bytes in Elixir; the golden fixtures under
# scripts/fixtures/jcs/ pin the two implementations to each other. Anything
# changed here must change there in the same release.

MAX_SAFE_INTEGER = 2**53 - 1
_JCS_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}
_REPR_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$")


def json_loads_strict(text):
    """json.loads that REFUSES duplicate object keys.

    Python keeps the last duplicate silently, which would let two manifests with
    different meanings canonicalize to the same bytes (M27 §7.6: parsers reject
    duplicate object keys before canonicalization).
    """

    def object_pairs(pairs):
        seen = set()
        for key, _ in pairs:
            if key in seen:
                raise JcsError(f"duplicate object key {key!r}")
            seen.add(key)
        return dict(pairs)

    return json.loads(text, object_pairs_hook=object_pairs)


def jcs_dumps(value) -> str:
    """Canonical JSON text per RFC 8785: sorted keys, minimal numbers, no whitespace."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _jcs_number(value)
    if isinstance(value, str):
        return _jcs_string(value)
    if isinstance(value, list):
        return "[" + ",".join(jcs_dumps(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(_jcs_member(key, val) for key, val in _jcs_sorted(value)) + "}"
    raise JcsError(f"value of type {type(value).__name__} is not JSON")


def jcs_bytes(value) -> bytes:
    return jcs_dumps(value).encode("utf-8")


def _jcs_member(key, value):
    return _jcs_string(key) + ":" + jcs_dumps(value)


def _jcs_sorted(obj):
    """Object keys sort by UTF-16 code unit — not by code point. Comparing
    UTF-16BE bytes reproduces that order exactly, so an astral key (a surrogate
    pair starting 0xD800..0xDBFF) sorts BEFORE U+E000..U+FFFF."""
    for key in obj:
        if not isinstance(key, str):
            raise JcsError(f"object key {key!r} is not a string")
    return sorted(obj.items(), key=lambda item: item[0].encode("utf-16-be", "surrogatepass"))


def _jcs_string(value: str) -> str:
    out = ['"']
    for char in value:
        if char in _JCS_ESCAPES:
            out.append(_JCS_ESCAPES[char])
        elif char < " ":
            out.append("\\u%04x" % ord(char))
        elif "\ud800" <= char <= "\udfff":
            raise JcsError(f"unpaired surrogate U+{ord(char):04X} in string")
        else:
            out.append(char)  # incl. DEL and every non-ASCII char, emitted as UTF-8
    out.append('"')
    return "".join(out)


def _jcs_number(value) -> str:
    """ECMAScript Number::toString, which is what RFC 8785 mandates."""
    if isinstance(value, int):
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise JcsError(f"integer {value} exceeds IEEE-754 double precision")
        return str(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise JcsError(f"{value} is not a JSON number")
    if value == 0.0:
        return "0"  # -0 serializes as 0
    if value < 0:
        return "-" + _jcs_number(-value)
    digits, exponent = _shortest_digits(value)
    return _es_format(digits, exponent)


def _shortest_digits(value: float):
    """Shortest round-trip digits `s` (k of them) and `n` with value = s×10^(n−k)."""
    match = _REPR_RE.match(repr(value))
    if match is None:
        raise JcsError(f"cannot canonicalize float {value!r}")
    integer, fraction, exponent = match.group(1), match.group(2) or "", match.group(3)
    scale = (int(exponent) if exponent else 0) - len(fraction)
    digits = (integer + fraction).lstrip("0")
    stripped = digits.rstrip("0")
    scale += len(digits) - len(stripped)
    return stripped, scale + len(stripped)


def _es_format(digits: str, n: int) -> str:
    k = len(digits)
    if k <= n <= 21:
        return digits + "0" * (n - k)
    if 0 < n <= 21:
        return digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return "0." + "0" * (-n) + digits
    exponent = n - 1
    mantissa = digits if k == 1 else digits[0] + "." + digits[1:]
    return f"{mantissa}e{'+' if exponent >= 0 else '-'}{abs(exponent)}"


def canonical_descriptor(name, parameters, output_schema, upstream_annotations) -> bytes:
    """The signed MCP security descriptor, canonicalized (M27 §7.6)."""
    return jcs_bytes(
        {
            "name": name,
            "inputSchema": parameters,
            "outputSchema": output_schema,
            "annotations": upstream_annotations,
        }
    )


def descriptor_sha256(name, parameters, output_schema, upstream_annotations) -> str:
    return hashlib.sha256(
        canonical_descriptor(name, parameters, output_schema, upstream_annotations)
    ).hexdigest()


# --- tree_digest_v2 (M27 §9.3) ----------------------------------------------

TREE_DIGEST_V2_PREFIX = b"fermix-plugin-tree-v2\0"


def tree_digest_v2(root: Path) -> str:
    """Unambiguous digest of a plugin tree.

    SHA-256 over the domain prefix, a big-endian u32 file count, then per file in
    bytewise-sorted normalized (NFC) UTF-8 relative-path order:
    ``u32 path_length || path_bytes || u64 content_length || content_bytes``.
    Directories and filesystem metadata are excluded; links are refused (safe
    extraction already forbids them).
    """
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValidationError(f"{path}: tree_digest_v2 refuses links")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValidationError(f"{path}: tree_digest_v2 refuses non-regular files")
        rel = unicodedata.normalize("NFC", path.relative_to(root).as_posix())
        entries.append((rel.encode("utf-8"), path.read_bytes()))
    return tree_digest_v2_of(entries)


def tree_digest_v2_of(entries) -> str:
    """tree_digest_v2 over (path_bytes, content_bytes) pairs, sorted bytewise."""
    ordered = sorted(entries, key=lambda entry: entry[0])
    paths = [path for path, _ in ordered]
    if len(set(paths)) != len(paths):
        raise ValidationError("tree_digest_v2: duplicate normalized path in the tree")
    digest = hashlib.sha256()
    digest.update(TREE_DIGEST_V2_PREFIX)
    digest.update(struct.pack(">I", len(ordered)))
    for path, content in ordered:
        digest.update(struct.pack(">I", len(path)))
        digest.update(path)
        digest.update(struct.pack(">Q", len(content)))
        digest.update(content)
    return digest.hexdigest()


def tree_digest_v2_of_mapping(files) -> str:
    """tree_digest_v2 over a {relative path: bytes} mapping (fixture/mem path)."""
    return tree_digest_v2_of(
        [(unicodedata.normalize("NFC", path).encode("utf-8"), content) for path, content in files.items()]
    )


def load_fixture(path: Path) -> dict:
    """Read a golden fixture, refusing duplicate keys like every other parse."""
    return json_loads_strict(Path(path).read_text())


def b64(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def git_show(ref_path: str) -> bytes:
    """`git show <ref>:<path>` as bytes; raises ValidationError on failure."""
    result = subprocess.run(["git", "show", ref_path], capture_output=True, check=False)
    if result.returncode != 0:
        raise ValidationError(f"git show {ref_path}: {result.stderr.decode().strip()}")
    return result.stdout
