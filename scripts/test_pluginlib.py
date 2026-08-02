#!/usr/bin/env python3
"""Unit tests for the publish-side validation boundary in pluginlib.

Focus: a manifest must not be able to point skills/interface assets outside the
plugin directory, runtime.command must be a bare executable name, and the
plugin-api-3 remote-MCP grammar (M27 §7.2/§7.5/§7.6/§9.3) must refuse every
shape core refuses at install. These mirror the core decoder's install-time
guards; keep them in sync.

Run: python3 scripts/test_pluginlib.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_plugin_package  # noqa: E402
import pluginlib  # noqa: E402
import validate_plugin  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
CHECK_PACKAGE = Path(__file__).parent / "check_plugin_package.py"
VALIDATE = Path(__file__).parent / "validate_plugin.py"


class Assertions(unittest.TestCase):
    """Shared error-list assertions; every validator accumulates, never raises."""

    def assert_error(self, errors, needle):
        self.assertTrue(any(needle in e for e in errors), f"expected {needle!r} in {errors}")

    def assert_no_error(self, errors, needle):
        self.assertFalse(any(needle in e for e in errors), f"unexpected {needle!r} in {errors}")

    def assert_clean(self, errors):
        self.assertEqual(errors, [])


class TempPlugin(Assertions):
    """A plugin directory materialized on disk, named after the manifest."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def materialize(self, manifest, extra_files=None, mode_bits=None):
        plugin_dir = self.root / manifest["name"]
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest, indent=2))
        for rel, content in (extra_files or {}).items():
            target = plugin_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content if isinstance(content, bytes) else content.encode())
            if mode_bits and rel in mode_bits:
                target.chmod(mode_bits[rel])
        return plugin_dir


# --- manifest builders -------------------------------------------------------

PLUGIN = "acme"


def remote_tool(name, **overrides):
    """One signed remote MCP tool; descriptor_sha256 is computed unless overridden."""
    tool = {
        "name": name,
        "description": f"Tool {name}.",
        "policy_class": "external_api",
        "read_only": True,
        "replay_safe": False,
        "required_credential_scope": "read",
        "rail": "mcp",
        "collection_policy": None,
        "argument_guards": [],
        "parameters": {
            "type": "object",
            "properties": {"workspaceId": {"type": "string"}},
            "required": ["workspaceId"],
        },
        "output_schema": None,
        "upstream_annotations": None,
    }
    tool.update(overrides)
    if "descriptor_sha256" not in overrides:
        tool["descriptor_sha256"] = pluginlib.descriptor_sha256(
            tool["name"], tool["parameters"], tool["output_schema"], tool["upstream_annotations"]
        )
    return tool


def setup_tool():
    return remote_tool(
        f"{PLUGIN}_list_workspaces",
        description="List workspaces available to the token.",
        parameters={"type": "object", "properties": {}},
    )


def remote_manifest(**overrides):
    manifest = {
        "schema_version": 2,
        "name": PLUGIN,
        "display_name": "Acme",
        "description": "Search and capture knowledge in an Acme workspace.",
        "category": "productivity",
        "version": "1.0.0",
        "min_core_version": "0.8.0",
        "auth": {
            "type": "api_key",
            "key_name": "ACME_PERSONAL_ACCESS_TOKEN",
            "header": "Authorization",
            "scheme": "Bearer",
            "prompt": "Paste an Acme personal access token",
            "validation": {
                "prefix": "acme_pat_",
                "min_bytes": 16,
                "max_bytes": 512,
                "charset": "visible_ascii",
                "forbid_whitespace": True,
            },
        },
        "runtime": {
            "kind": "remote_mcp",
            "transport": "streamable_http",
            "protocol_version": "2025-06-18",
            "base_url": "https://mcp.acme.example",
            "mcp_path": "/mcp",
            "tool_name_mode": "preserve",
        },
        "tool_profiles": [
            {
                "name": "retrieval",
                "display_name": "Retrieval only",
                "default": True,
                "required_credential_scope": "read",
                "scope_visibility": "none",
                "tools": [f"{PLUGIN}_search"],
            },
            {
                "name": "capture",
                "display_name": "Retrieval and capture",
                "default": False,
                "required_credential_scope": "write",
                "scope_visibility": "none",
                "tools": [f"{PLUGIN}_search", f"{PLUGIN}_append"],
            },
        ],
        "setup_tools": [f"{PLUGIN}_list_workspaces"],
        "resource_scope": {
            "kind": "single_workspace",
            "discovery_tool": f"{PLUGIN}_list_workspaces",
            "id_field": "id",
            "label_field": "name",
            "argument": "workspaceId",
        },
        "budgets": {"agent_turn_calls": 20, "agent_turn_paginated_calls": 5},
        "result_contract": {
            "kind": "json_boolean",
            "success_field": "ok",
            "status_field": "status",
            "message_field": "message",
        },
        "tools": [
            setup_tool(),
            remote_tool(f"{PLUGIN}_search"),
            remote_tool(
                f"{PLUGIN}_append",
                description="Append Markdown to an existing note.",
                read_only=False,
                required_credential_scope="write",
            ),
        ],
        "plugin_api": 3,
    }
    manifest.update(overrides)
    return manifest


def api2_manifest(**overrides):
    manifest = {
        "schema_version": 2,
        "name": PLUGIN,
        "display_name": "Acme",
        "description": "An http-rail plugin.",
        "category": "productivity",
        "version": "1.0.0",
        "min_core_version": "0.5.0",
        "auth": {"type": "api_key", "key_name": "ACME_API_KEY", "header": "Authorization", "prompt": "Paste a key"},
        "tools": [
            {
                "name": f"{PLUGIN}_search",
                "description": "Search Acme.",
                "policy_class": "external_api",
                "read_only": True,
                "rail": "http",
                "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
                "request": {"method": "GET", "url": "https://api.acme.example/search"},
            }
        ],
        "plugin_api": 2,
    }
    manifest.update(overrides)
    return manifest


def runtime_of(**overrides):
    runtime = dict(remote_manifest()["runtime"])
    runtime.update(overrides)
    return runtime


# --- existing plugin-api-2 guards (unchanged) --------------------------------


class PathWithin(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_in_dir_paths_are_allowed(self):
        self.assertTrue(pluginlib._path_within(self.dir, "assets/logo.png"))
        self.assertTrue(pluginlib._path_within(self.dir, "skills/x/SKILL.md"))

    def test_traversal_and_absolute_are_rejected(self):
        self.assertFalse(pluginlib._path_within(self.dir, "../secret.png"))
        self.assertFalse(pluginlib._path_within(self.dir, "../../etc/passwd"))
        self.assertFalse(pluginlib._path_within(self.dir, "/etc/passwd"))
        self.assertFalse(pluginlib._path_within(self.dir, ""))


class ValidateSkills(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_escaping_skill_path_is_rejected_even_if_target_exists(self):
        (self.dir.parent / "outside.md").write_text("x")
        manifest = {"name": "p", "skills": [{"name": "s", "path": "../outside.md"}]}
        errors = pluginlib._validate_skills(manifest, self.dir)
        self.assertTrue(any("must stay inside" in e for e in errors), errors)

    def test_in_dir_skill_path_is_accepted(self):
        skill = self.dir / "skills" / "p-plugin"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x")
        manifest = {"name": "p", "skills": [{"name": "s", "path": "skills/p-plugin/SKILL.md"}]}
        self.assertEqual(pluginlib._validate_skills(manifest, self.dir), [])


class ValidateInterface(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_escaping_logo_is_rejected(self):
        (self.dir.parent / "secret.png").write_text("x")
        manifest = {"interface": {"logo": "../secret.png"}}
        errors = pluginlib._validate_interface(manifest, self.dir)
        self.assertTrue(any("must stay inside" in e for e in errors), errors)

    def test_in_dir_logo_is_accepted(self):
        assets = self.dir / "assets"
        assets.mkdir()
        (assets / "logo.png").write_text("x")
        manifest = {"interface": {"logo": "assets/logo.png"}}
        self.assertEqual(pluginlib._validate_interface(manifest, self.dir), [])


class ValidateRuntimeCommand(unittest.TestCase):
    def _manifest(self, command):
        return {
            "tools": [{"rail": "mcp"}],
            "runtime": {"kind": "node", "command": command, "vendored": True},
        }

    def test_traversal_and_absolute_commands_are_rejected(self):
        for command in ("../../../../bin/sh", "/bin/sh", "bin/server", "..", "."):
            errors = pluginlib._validate_runtime(self._manifest(command))
            self.assertTrue(
                any("bare executable name" in e for e in errors),
                f"{command!r} should be rejected: {errors}",
            )

    def test_bare_command_is_accepted(self):
        errors = pluginlib._validate_runtime(self._manifest("node"))
        self.assertFalse(any("command" in e for e in errors), errors)


# --- 1. schema_version: refuse an unknown major ------------------------------


class SchemaVersionMajor(Assertions):
    def _errors(self, value):
        manifest = api2_manifest(schema_version=value)
        return pluginlib._validate_top_fields(manifest, Path(PLUGIN))

    def test_unknown_major_is_refused(self):
        for value in (3, 4, 1, "2", 2.0, None):
            self.assert_error(self._errors(value), "schema_version must be exactly 2")

    def test_schema_version_3_message_says_it_is_not_parsed_as_2(self):
        self.assert_error(self._errors(3), "an unknown schema major is refused")

    def test_schema_version_2_is_accepted(self):
        self.assert_no_error(self._errors(2), "schema_version")


# --- 2/3. plugin-api gating: api 2 must reject every api-3-only field ---------


class ApiGating(Assertions):
    def test_api2_rejects_every_api3_only_root_field(self):
        samples = {
            "tool_profiles": [],
            "setup_tools": [],
            "resource_scope": {},
            "budgets": {},
            "result_contract": {},
        }
        self.assertEqual(set(samples), pluginlib.API3_ONLY_ROOT_FIELDS)
        for field, value in samples.items():
            errors = pluginlib._validate_api_gating(api2_manifest(**{field: value}))
            self.assert_error(errors, f"{field} requires plugin_api >= 3")

    def test_api2_rejects_auth_validation(self):
        auth = dict(api2_manifest()["auth"], validation={"prefix": "acme_"})
        errors = pluginlib._validate_api_gating(api2_manifest(auth=auth))
        self.assert_error(errors, "auth.validation requires plugin_api >= 3")

    def test_api2_rejects_every_api3_only_runtime_field(self):
        for field, value in (
            ("transport", "streamable_http"),
            ("protocol_version", "2025-06-18"),
            ("base_url", "https://mcp.acme.example"),
            ("mcp_path", "/mcp"),
            ("tool_name_mode", "preserve"),
        ):
            runtime = {"kind": "node", "command": "node", "vendored": True, field: value}
            errors = pluginlib._validate_api_gating(api2_manifest(runtime=runtime))
            self.assert_error(errors, f"runtime.{field} requires plugin_api >= 3")

    def test_api2_rejects_remote_mcp_kind(self):
        errors = pluginlib._validate_api_gating(api2_manifest(runtime=runtime_of()))
        self.assert_error(errors, "runtime.kind 'remote_mcp' requires plugin_api >= 3")

    def test_api2_rejects_every_api3_only_tool_field(self):
        samples = {
            "replay_safe": True,
            "required_credential_scope": "read",
            "collection_policy": None,
            "argument_guards": [],
            "output_schema": None,
            "upstream_annotations": None,
            "descriptor_sha256": "0" * 64,
        }
        self.assertEqual(set(samples), pluginlib.API3_ONLY_TOOL_FIELDS)
        for field, value in samples.items():
            manifest = api2_manifest()
            manifest["tools"][0][field] = value
            errors = pluginlib._validate_api_gating(manifest)
            self.assert_error(errors, f"{field} requires plugin_api >= 3")

    def test_preserve_tool_name_mode_is_refused_under_api2(self):
        runtime = {"kind": "node", "command": "node", "vendored": True, "tool_name_mode": "preserve"}
        errors = pluginlib._validate_api_gating(api2_manifest(runtime=runtime))
        self.assert_error(errors, "runtime.tool_name_mode requires plugin_api >= 3")

    def test_api3_manifest_passes_gating(self):
        self.assert_clean(pluginlib._validate_api_gating(remote_manifest()))

    def test_plain_api2_manifest_passes_gating(self):
        self.assert_clean(pluginlib._validate_api_gating(api2_manifest()))


# --- 2. remote runtime shape -------------------------------------------------


class RemoteRuntimeShape(Assertions):
    def _errors(self, **runtime_overrides):
        return pluginlib._validate_runtime(remote_manifest(runtime=runtime_of(**runtime_overrides)))

    def test_valid_remote_runtime_is_accepted(self):
        self.assert_clean(pluginlib._validate_runtime(remote_manifest()))

    def test_local_process_fields_are_mutually_exclusive(self):
        for field, value in (
            ("command", "node"),
            ("args", ["server.js"]),
            ("env", {"A": "1"}),
            ("pass_env", ["PATH"]),
            ("cwd", "src"),
            ("vendored", True),
            ("min_version", "18.0.0"),
        ):
            errors = self._errors(**{field: value})
            self.assert_error(errors, f"runtime.{field} is not allowed with runtime.kind 'remote_mcp'")
        self.assertEqual(
            pluginlib.LOCAL_RUNTIME_FIELDS,
            {"command", "args", "env", "pass_env", "cwd", "vendored", "min_version"},
        )

    def test_transport_must_be_streamable_http(self):
        for value in ("stdio", "sse", "http", None):
            self.assert_error(self._errors(transport=value), "runtime.transport must be exactly 'streamable_http'")

    def test_protocol_version_must_be_exact(self):
        for value in ("2025-03-26", "2025-06-18 ", 20250618, None):
            self.assert_error(self._errors(protocol_version=value), "runtime.protocol_version must be exactly")

    def test_unknown_runtime_key_is_refused(self):
        self.assert_error(self._errors(headers={"X-Debug": "1"}), "runtime has unknown key 'headers'")

    def test_remote_runtime_needs_an_mcp_rail_tool(self):
        manifest = remote_manifest()
        for tool in manifest["tools"]:
            tool["rail"] = "http"
        self.assert_error(pluginlib._validate_runtime(manifest), "no tool has rail: mcp")

    def test_remote_tools_must_ride_the_mcp_rail(self):
        manifest = remote_manifest()
        manifest["tools"][1]["rail"] = "http"
        self.assert_error(pluginlib._validate_remote_contract(manifest), "rail must be 'mcp'")


class RemoteBaseUrl(Assertions):
    def _errors(self, base_url):
        return pluginlib._validate_base_url(base_url)

    def test_https_origin_is_accepted(self):
        for value in ("https://mcp.acme.example", "https://a.b.c.example:8443", "https://Example.COM"):
            self.assert_clean(self._errors(value))

    def test_non_https_is_refused(self):
        for value in ("http://mcp.acme.example", "ws://mcp.acme.example", "mcp.acme.example", "HTTPS://x.example"):
            self.assert_error(self._errors(value), "must use the https:// scheme")

    def test_userinfo_template_and_wildcard_are_refused(self):
        self.assert_error(self._errors("https://user:pw@mcp.acme.example"), "userinfo is refused")
        self.assert_error(self._errors("https://{host}.acme.example"), "template is refused")
        self.assert_error(self._errors("https://*.acme.example"), "wildcard is refused")

    def test_path_query_and_fragment_are_refused(self):
        self.assert_error(self._errors("https://mcp.acme.example/"), "must be an origin with no path")
        self.assert_error(self._errors("https://mcp.acme.example/mcp"), "must be an origin with no path")
        self.assert_error(self._errors("https://mcp.acme.example?x=1"), "must be an origin with no query")
        self.assert_error(self._errors("https://mcp.acme.example#f"), "must be an origin with no fragment")

    def test_empty_host_and_port_tricks_are_refused(self):
        self.assert_error(self._errors("https://"), "must have a non-empty host")
        self.assert_error(self._errors("https://:443"), "must have a non-empty host")
        self.assert_error(self._errors("https://mcp.acme.example:"), "port must be a decimal 1-65535")
        self.assert_error(self._errors("https://mcp.acme.example:0"), "port must be a decimal 1-65535")
        self.assert_error(self._errors("https://mcp.acme.example:0443"), "port must be a decimal 1-65535")
        self.assert_error(self._errors("https://mcp.acme.example:99999"), "port must be a decimal 1-65535")
        self.assert_error(self._errors("https://mcp.acme.example:https"), "port must be a decimal 1-65535")

    def test_ip_literals_are_refused(self):
        for value in (
            "https://93.184.216.34",
            "https://127.0.0.1",
            "https://93.184.216.34:8443",
            "https://[2606:2800:220:1:248:1893:25c8:1946]",
            "https://[::1]:443",
            "https://acme.example.1",
        ):
            self.assert_error(self._errors(value), "not an IP literal")

    def test_malformed_hosts_are_refused(self):
        for value in ("https://-acme.example", "https://acme..example", "https://acme example"):
            self.assert_error(self._errors(value), "must be a literal DNS hostname")


class RemoteMcpPath(Assertions):
    def _errors(self, mcp_path):
        return pluginlib._validate_mcp_path(mcp_path)

    def test_literal_absolute_path_is_accepted(self):
        for value in ("/mcp", "/v1/mcp", "/a-b_c.d~e"):
            self.assert_clean(self._errors(value))

    def test_relative_or_missing_path_is_refused(self):
        self.assert_error(self._errors("mcp"), "must be an absolute path")
        self.assert_error(self._errors(""), "runtime.mcp_path is required")
        self.assert_error(self._errors(None), "runtime.mcp_path is required")

    def test_query_fragment_backslash_and_template_are_refused(self):
        self.assert_error(self._errors("/mcp?x=1"), "query is refused")
        self.assert_error(self._errors("/mcp#f"), "fragment is refused")
        self.assert_error(self._errors("/mcp\\x"), "backslash is refused")
        self.assert_error(self._errors("/{tenant}/mcp"), "template is refused")

    def test_dot_segments_and_encoded_slashes_are_refused(self):
        self.assert_error(self._errors("/../mcp"), "no '.' or '..' segment")
        self.assert_error(self._errors("/a/./mcp"), "no '.' or '..' segment")
        self.assert_error(self._errors("/a%2fb"), "percent-encoded slash")
        self.assert_error(self._errors("/a%2Fb"), "percent-encoded slash")

    def test_empty_segments_and_whitespace_are_refused(self):
        self.assert_error(self._errors("//mcp"), "no empty segment")
        self.assert_error(self._errors("/mcp/"), "no empty segment")
        self.assert_error(self._errors("/mcp x"), "visible ASCII")


class ToolNameMode(Assertions):
    def test_preserve_requires_every_tool_namespaced(self):
        manifest = remote_manifest()
        manifest["tools"].append(remote_tool("search_everything"))
        errors = pluginlib._validate_tool_name_mode(manifest, "preserve")
        self.assert_error(errors, "requires every declared tool to start with 'acme_'")

    def test_preserve_is_accepted_when_every_tool_is_namespaced(self):
        self.assert_clean(pluginlib._validate_tool_name_mode(remote_manifest(), "preserve"))

    def test_prefix_mode_is_accepted(self):
        self.assert_clean(pluginlib._validate_tool_name_mode(remote_manifest(), "prefix"))

    def test_unknown_mode_is_refused(self):
        for value in ("hash", "none", None, "PRESERVE"):
            errors = pluginlib._validate_tool_name_mode(remote_manifest(), value)
            self.assert_error(errors, "runtime.tool_name_mode must be one of")

    def local_manifest(self, mode):
        return {
            "name": PLUGIN,
            "plugin_api": 3,
            "tools": [{"rail": "mcp", "name": f"{PLUGIN}_x"}],
            "runtime": {"kind": "node", "command": "node", "vendored": True, "tool_name_mode": mode},
        }

    def test_preserve_is_refused_for_a_local_runtime(self):
        errors = pluginlib._validate_runtime(self.local_manifest("preserve"))
        self.assert_error(errors, "must be 'prefix' for a local runtime")

    def test_prefix_is_accepted_for_a_local_runtime(self):
        self.assert_clean(pluginlib._validate_runtime(self.local_manifest("prefix")))


# --- 4. remote auth ----------------------------------------------------------


class RemoteAuth(Assertions):
    def _errors(self, **auth_overrides):
        auth = dict(remote_manifest()["auth"])
        auth.update(auth_overrides)
        return pluginlib._validate_auth(remote_manifest(auth=auth))

    def test_valid_remote_auth_is_accepted(self):
        self.assert_clean(self._errors())

    def test_header_and_scheme_match_case_insensitively(self):
        self.assert_clean(self._errors(header="authorization", scheme="bearer"))
        self.assert_clean(self._errors(header="AUTHORIZATION", scheme="BEARER"))

    def test_only_api_key_auth_is_accepted(self):
        self.assert_error(self._errors(type="oauth2"), "remote_mcp v1 requires auth.type 'api_key'")
        self.assert_error(self._errors(type="none"), "remote_mcp v1 requires auth.type 'api_key'")

    def test_other_headers_and_schemes_are_refused(self):
        self.assert_error(self._errors(header="X-Api-Key"), "requires auth.header 'Authorization'")
        self.assert_error(self._errors(scheme="Token"), "requires auth.scheme 'Bearer'")
        self.assert_error(self._errors(scheme=None), "requires auth.scheme 'Bearer'")


class AuthValidationBlock(Assertions):
    def _errors(self, validation):
        return pluginlib._validate_auth_validation(validation)

    def test_bounded_declarative_block_is_accepted(self):
        self.assert_clean(
            self._errors(
                {
                    "prefix": "acme_pat_",
                    "min_bytes": 16,
                    "max_bytes": 512,
                    "charset": "visible_ascii",
                    "forbid_whitespace": True,
                }
            )
        )

    def test_unknown_key_is_refused(self):
        for key in ("regex", "pattern", "validator", "command", "script"):
            self.assert_error(self._errors({key: "x"}), f"auth.validation has unknown key {key!r}")

    def test_regex_looking_prefix_is_refused(self):
        for value in ("^acme_pat_", "acme_(pat|tok)_", "acme_.*", "acme_pat_[0-9]+"):
            self.assert_error(self._errors({"prefix": value}), "must be a literal string, not a pattern")

    def test_empty_or_whitespace_prefix_is_refused(self):
        self.assert_error(self._errors({"prefix": ""}), "non-empty literal string")
        self.assert_error(self._errors({"prefix": 7}), "non-empty literal string")
        self.assert_error(self._errors({"prefix": "acme pat"}), "visible ASCII with no whitespace")

    def test_byte_bounds_must_be_positive_and_ordered(self):
        self.assert_error(self._errors({"min_bytes": 0}), "must be a positive integer")
        self.assert_error(self._errors({"max_bytes": -1}), "must be a positive integer")
        self.assert_error(self._errors({"min_bytes": True}), "must be a positive integer")
        self.assert_error(self._errors({"min_bytes": 512, "max_bytes": 16}), "must not exceed")

    def test_charset_is_a_fixed_enum(self):
        self.assert_error(self._errors({"charset": "utf8"}), "auth.validation.charset must be one of")

    def test_forbid_whitespace_must_be_boolean(self):
        self.assert_error(self._errors({"forbid_whitespace": "yes"}), "must be a boolean")


# --- 5/6/7. profiles, setup tools, resource scope ----------------------------


class ToolProfiles(Assertions):
    def _errors(self, profiles):
        return pluginlib._validate_remote_contract(remote_manifest(tool_profiles=profiles))

    def test_valid_profiles_are_accepted(self):
        self.assert_clean(pluginlib._validate_remote_contract(remote_manifest()))

    def test_profiles_are_required_and_non_empty(self):
        manifest = remote_manifest()
        del manifest["tool_profiles"]
        self.assert_error(
            pluginlib._validate_remote_contract(manifest), "tool_profiles is required for a remote_mcp plugin"
        )
        self.assert_error(self._errors([]), "tool_profiles must be a non-empty list")

    def test_exactly_one_default(self):
        profiles = remote_manifest()["tool_profiles"]
        profiles[1]["default"] = True
        self.assert_error(self._errors(profiles), "exactly one tool_profiles entry must set default: true (found 2)")
        profiles[0]["default"] = False
        profiles[1]["default"] = False
        self.assert_error(self._errors(profiles), "(found 0)")

    def test_profile_field_grammar(self):
        profiles = remote_manifest()["tool_profiles"]
        profiles[0]["name"] = "Retrieval Only"
        self.assert_error(self._errors(profiles), "name must match")
        profiles = remote_manifest()["tool_profiles"]
        profiles[0]["display_name"] = ""
        self.assert_error(self._errors(profiles), "display_name must be a non-empty string")
        profiles = remote_manifest()["tool_profiles"]
        profiles[0]["default"] = "true"
        self.assert_error(self._errors(profiles), "default must be a boolean")
        profiles = remote_manifest()["tool_profiles"]
        profiles[0]["required_credential_scope"] = "admin"
        self.assert_error(self._errors(profiles), "required_credential_scope must be one of")
        profiles = remote_manifest()["tool_profiles"]
        profiles[0]["scope_visibility"] = "some"
        self.assert_error(self._errors(profiles), "scope_visibility must be one of")

    def test_unknown_profile_field_is_refused(self):
        profiles = remote_manifest()["tool_profiles"]
        profiles[0]["hidden"] = True
        self.assert_error(self._errors(profiles), "unknown field 'hidden'")

    def test_duplicate_profile_name_is_refused(self):
        profiles = remote_manifest()["tool_profiles"]
        profiles[1]["name"] = "retrieval"
        self.assert_error(self._errors(profiles), "duplicate profile name")

    def test_profile_tools_must_be_declared_and_non_empty(self):
        profiles = remote_manifest()["tool_profiles"]
        profiles[0]["tools"] = []
        self.assert_error(self._errors(profiles), "tools must be a non-empty list of declared tool names")
        profiles = remote_manifest()["tool_profiles"]
        profiles[0]["tools"] = ["acme_missing"]
        self.assert_error(self._errors(profiles), "tool 'acme_missing' is not declared in tools")

    def test_profile_tool_must_not_be_a_setup_tool(self):
        profiles = remote_manifest()["tool_profiles"]
        profiles[0]["tools"] = ["acme_search", "acme_list_workspaces"]
        self.assert_error(self._errors(profiles), "is a setup_tools member and must not appear in a profile")

    def test_duplicate_tool_in_one_profile_is_refused(self):
        profiles = remote_manifest()["tool_profiles"]
        profiles[0]["tools"] = ["acme_search", "acme_search"]
        self.assert_error(self._errors(profiles), "duplicate tool 'acme_search'")


class SetupToolsAndResourceScope(Assertions):
    def _errors(self, **overrides):
        return pluginlib._validate_remote_contract(remote_manifest(**overrides))

    def test_setup_tools_must_be_declared(self):
        self.assert_error(self._errors(setup_tools=["acme_nope"]), "tool 'acme_nope' is not declared in tools")

    def test_duplicate_setup_tool_is_refused(self):
        self.assert_error(
            self._errors(setup_tools=["acme_list_workspaces", "acme_list_workspaces"]),
            "setup_tools: duplicate tool",
        )

    def test_discovery_tool_must_be_a_setup_tool(self):
        scope = dict(remote_manifest()["resource_scope"], discovery_tool="acme_search")
        self.assert_error(self._errors(resource_scope=scope), "must be a setup_tools member")

    def test_discovery_tool_must_be_declared(self):
        scope = dict(remote_manifest()["resource_scope"], discovery_tool="acme_ghost")
        self.assert_error(self._errors(resource_scope=scope), "is not declared in tools")

    def test_scope_fields_must_be_non_empty_strings(self):
        for field in ("id_field", "label_field", "argument"):
            scope = dict(remote_manifest()["resource_scope"], **{field: ""})
            self.assert_error(self._errors(resource_scope=scope), f"resource_scope.{field} must be a non-empty string")

    def test_scope_kind_and_unknown_field(self):
        scope = dict(remote_manifest()["resource_scope"], kind="many_workspaces")
        self.assert_error(self._errors(resource_scope=scope), "resource_scope.kind must be one of")
        scope = dict(remote_manifest()["resource_scope"], extra=1)
        self.assert_error(self._errors(resource_scope=scope), "unknown field 'extra'")

    def test_scope_argument_must_appear_in_every_profile_tool(self):
        manifest = remote_manifest()
        manifest["tools"][1]["parameters"] = {"type": "object", "properties": {"query": {"type": "string"}}}
        manifest["tools"][1]["descriptor_sha256"] = pluginlib.descriptor_sha256(
            manifest["tools"][1]["name"], manifest["tools"][1]["parameters"], None, None
        )
        errors = pluginlib._validate_remote_contract(manifest)
        self.assert_error(errors, "parameters.properties must declare the resource_scope argument 'workspaceId'")

    def test_setup_tool_need_not_declare_the_scope_argument(self):
        # The discovery tool runs BEFORE a workspace is chosen.
        self.assert_clean(pluginlib._validate_remote_contract(remote_manifest()))


# --- 8/9. budgets and result contract ----------------------------------------


class Budgets(Assertions):
    def _errors(self, budgets):
        return pluginlib._validate_budgets(remote_manifest(budgets=budgets), True)

    def test_valid_budgets(self):
        self.assert_clean(self._errors({"agent_turn_calls": 20, "agent_turn_paginated_calls": 5}))
        self.assert_clean(self._errors({"agent_turn_calls": 1, "agent_turn_paginated_calls": 1}))
        self.assert_clean(self._errors({"agent_turn_calls": 100, "agent_turn_paginated_calls": 100}))

    def test_bounds(self):
        self.assert_error(self._errors({"agent_turn_calls": 0, "agent_turn_paginated_calls": 1}), "1..100")
        self.assert_error(self._errors({"agent_turn_calls": 101, "agent_turn_paginated_calls": 1}), "1..100")
        self.assert_error(self._errors({"agent_turn_calls": 20, "agent_turn_paginated_calls": 0}), "1..100")
        self.assert_error(self._errors({"agent_turn_calls": True, "agent_turn_paginated_calls": 1}), "1..100")
        self.assert_error(self._errors({"agent_turn_calls": 20}), "agent_turn_paginated_calls must be an integer")

    def test_paginated_calls_may_not_exceed_total_calls(self):
        errors = self._errors({"agent_turn_calls": 5, "agent_turn_paginated_calls": 6})
        self.assert_error(errors, "agent_turn_paginated_calls must not exceed budgets.agent_turn_calls")

    def test_unknown_budget_key_and_requirement(self):
        errors = self._errors({"agent_turn_calls": 20, "agent_turn_paginated_calls": 5, "tokens": 10})
        self.assert_error(errors, "budgets: unknown field 'tokens'")
        manifest = remote_manifest()
        del manifest["budgets"]
        self.assert_error(pluginlib._validate_remote_contract(manifest), "budgets is required for a remote_mcp plugin")


class ResultContract(Assertions):
    def _errors(self, contract):
        return pluginlib._validate_result_contract(remote_manifest(result_contract=contract), True)

    def test_valid_contract(self):
        self.assert_clean(
            self._errors(
                {"kind": "json_boolean", "success_field": "ok", "status_field": "status", "message_field": "message"}
            )
        )

    def test_kind_fields_and_unknown_key(self):
        base = {"kind": "json_boolean", "success_field": "ok", "status_field": "s", "message_field": "m"}
        self.assert_error(self._errors(dict(base, kind="xml")), "result_contract.kind must be one of")
        for field in ("success_field", "status_field", "message_field"):
            self.assert_error(self._errors(dict(base, **{field: ""})), f"result_contract.{field} must be a non-empty")
        self.assert_error(self._errors(dict(base, extra=1)), "result_contract: unknown field 'extra'")

    def test_contract_is_required_for_remote(self):
        manifest = remote_manifest()
        del manifest["result_contract"]
        self.assert_error(
            pluginlib._validate_remote_contract(manifest), "result_contract is required for a remote_mcp plugin"
        )


# --- 10/11. per-tool signed policy + descriptor hash -------------------------


class RemoteToolFields(Assertions):
    def _errors(self, **tool_overrides):
        manifest = remote_manifest()
        manifest["tools"][1] = remote_tool(f"{PLUGIN}_search", **tool_overrides)
        return pluginlib._validate_remote_contract(manifest)

    def test_valid_tool_is_accepted(self):
        self.assert_clean(self._errors())

    def test_every_required_field_is_required(self):
        for field in pluginlib.REMOTE_TOOL_REQUIRED_FIELDS:
            manifest = remote_manifest()
            del manifest["tools"][1][field]
            errors = pluginlib._validate_remote_contract(manifest)
            self.assert_error(errors, f"{field} is required for a remote_mcp tool")

    def test_policy_class_v1_is_external_api(self):
        self.assert_error(self._errors(policy_class="local_process"), "policy_class must be one of")

    def test_replay_safe_is_an_independent_boolean(self):
        self.assert_error(self._errors(replay_safe="no"), "replay_safe must be a boolean")
        self.assert_clean(self._errors(read_only=True, replay_safe=False))
        self.assert_clean(self._errors(read_only=False, replay_safe=True, required_credential_scope="write"))

    def test_required_credential_scope_enum(self):
        self.assert_error(self._errors(required_credential_scope="admin"), "required_credential_scope must be one of")

    def test_parameters_must_be_an_object_schema(self):
        self.assert_error(self._errors(parameters={"type": "string"}), "parameters must be an object schema")
        self.assert_error(self._errors(parameters="{}"), "parameters must be an object schema")

    def test_output_schema_and_annotations_are_object_or_null(self):
        self.assert_error(self._errors(output_schema="none"), "output_schema must be an object or null")
        self.assert_error(self._errors(upstream_annotations=[]), "upstream_annotations must be an object or null")
        self.assert_clean(self._errors(upstream_annotations={"title": "Search"}))

    def test_descriptor_sha256_must_be_64_lowercase_hex(self):
        for value in ("ABC", "0" * 63, "0" * 65, "A" * 64, 1234, None):
            self.assert_error(
                self._errors(descriptor_sha256=value), "descriptor_sha256 must be 64 lowercase hex characters"
            )

    def test_descriptor_sha256_must_match_the_canonical_descriptor(self):
        errors = self._errors(descriptor_sha256="f" * 64)
        self.assert_error(errors, "does not match the canonical descriptor")

    def test_descriptor_hash_covers_annotations_and_output_schema(self):
        tool = remote_tool(f"{PLUGIN}_search")
        signed = tool["descriptor_sha256"]
        drifted = pluginlib.descriptor_sha256(tool["name"], tool["parameters"], {"type": "object"}, None)
        self.assertNotEqual(signed, drifted)
        errors = self._errors(output_schema={"type": "object"}, descriptor_sha256=signed)
        self.assert_error(errors, "does not match the canonical descriptor")


class CollectionPolicy(Assertions):
    PARAMETERS = {
        "type": "object",
        "properties": {"workspaceId": {"type": "string"}, "limit": {"type": "integer"}},
    }
    OUTPUT = {"type": "object", "properties": {"items": {"type": "array"}}}

    def _errors(self, policy, parameters=None, output_schema=None):
        manifest = remote_manifest()
        manifest["tools"][1] = remote_tool(
            f"{PLUGIN}_search",
            parameters=parameters or self.PARAMETERS,
            output_schema=self.OUTPUT if output_schema is None else output_schema,
            collection_policy=policy,
        )
        return pluginlib._validate_remote_contract(manifest)

    def valid_policy(self, **overrides):
        policy = {
            "paginated": True,
            "request_limit_pointer": "/limit",
            "default_limit": 50,
            "result_items_pointer": "/items",
            "max_returned_items": 50,
        }
        policy.update(overrides)
        return policy

    def test_valid_policy_is_accepted(self):
        self.assert_clean(self._errors(self.valid_policy()))

    def test_null_policy_is_accepted(self):
        self.assert_clean(self._errors(None))

    def test_unknown_and_missing_keys_are_refused(self):
        self.assert_error(self._errors(self.valid_policy(cursor="/next")), "unknown key 'cursor'")
        policy = self.valid_policy()
        del policy["default_limit"]
        self.assert_error(self._errors(policy), "collection_policy.default_limit is required")

    def test_paginated_must_be_true(self):
        self.assert_error(self._errors(self.valid_policy(paginated=False)), "collection_policy.paginated must be true")

    def test_limits_are_bounded_1_to_100(self):
        for field in ("default_limit", "max_returned_items"):
            for value in (0, 101, True, "50"):
                self.assert_error(self._errors(self.valid_policy(**{field: value})), f"{field} must be an integer 1..100")

    def test_pointers_reject_wildcards_and_bad_syntax(self):
        self.assert_error(self._errors(self.valid_policy(result_items_pointer="/items/*")), "must not contain a wildcard")
        self.assert_error(self._errors(self.valid_policy(request_limit_pointer="limit")), "starting with '/'")
        self.assert_error(self._errors(self.valid_policy(request_limit_pointer="/a//b")), "empty reference token")
        self.assert_error(self._errors(self.valid_policy(request_limit_pointer="/a~2b")), "invalid '~' escape")
        self.assert_error(self._errors(self.valid_policy(request_limit_pointer="")), "non-empty RFC 6901")

    def test_pointers_must_resolve_in_the_signed_schemas(self):
        self.assert_error(
            self._errors(self.valid_policy(request_limit_pointer="/pageSize")),
            "does not resolve in the signed parameters",
        )
        self.assert_error(
            self._errors(self.valid_policy(result_items_pointer="/results")),
            "does not resolve in the signed output_schema",
        )

    def test_pointers_must_resolve_to_a_compatible_type(self):
        self.assert_error(
            self._errors(self.valid_policy(request_limit_pointer="/workspaceId")),
            "resolves to type 'string'",
        )
        output = {"type": "object", "properties": {"items": {"type": "object"}}}
        self.assert_error(self._errors(self.valid_policy(), output_schema=output), "resolves to type 'object'")

    def test_collection_policy_needs_a_signed_output_schema(self):
        self.assert_error(
            self._errors(self.valid_policy(), output_schema=False),
            "output_schema is not an object schema",
        )


class ArgumentGuards(Assertions):
    PARAMETERS = {
        "type": "object",
        "properties": {
            "workspaceId": {"type": "string"},
            "urls": {"type": "array", "items": {"type": "string"}},
        },
    }

    def _errors(self, guards, parameters=None):
        manifest = remote_manifest()
        manifest["tools"][1] = remote_tool(
            f"{PLUGIN}_search", parameters=parameters or self.PARAMETERS, argument_guards=guards
        )
        return pluginlib._validate_remote_contract(manifest)

    def test_valid_guard_is_accepted(self):
        for kind in pluginlib.ARGUMENT_GUARD_KINDS:
            self.assert_clean(self._errors([{"pointer": "/urls", "kind": kind, "max_items": 20}]))

    def test_empty_list_is_accepted(self):
        self.assert_clean(self._errors([]))

    def test_kind_is_a_fixed_core_guard(self):
        for kind in ("regex", "public_http_url", "custom", None):
            errors = self._errors([{"pointer": "/urls", "kind": kind, "max_items": 20}])
            self.assert_error(errors, "argument_guards kind must be one of")
            self.assert_error(errors, "the guards are fixed in core")

    def test_unknown_guard_key_is_refused(self):
        errors = self._errors([{"pointer": "/urls", "kind": "public_http_url_array", "max_items": 5, "allow": ["x"]}])
        self.assert_error(errors, "unknown key 'allow'")

    def test_max_items_is_bounded_1_to_100(self):
        for value in (0, 101, True, "5", None):
            errors = self._errors([{"pointer": "/urls", "kind": "public_http_url_array", "max_items": value}])
            self.assert_error(errors, "max_items must be an integer 1..100")

    def test_pointer_must_resolve_to_an_array_in_parameters(self):
        errors = self._errors([{"pointer": "/workspaceId", "kind": "public_http_url_array", "max_items": 5}])
        self.assert_error(errors, "resolves to type 'string'")
        errors = self._errors([{"pointer": "/missing", "kind": "public_http_url_array", "max_items": 5}])
        self.assert_error(errors, "does not resolve in the signed parameters")
        errors = self._errors([{"pointer": "/urls/*", "kind": "public_http_url_array", "max_items": 5}])
        self.assert_error(errors, "must not contain a wildcard")

    def test_guard_count_is_bounded(self):
        guards = [{"pointer": "/urls", "kind": "public_http_url_array", "max_items": 5}] * (
            pluginlib.MAX_ARGUMENT_GUARDS + 1
        )
        self.assert_error(self._errors(guards), f"at most {pluginlib.MAX_ARGUMENT_GUARDS} guards")

    def test_non_list_is_refused(self):
        self.assert_error(self._errors({"pointer": "/urls"}), "argument_guards must be a list")


# --- 11. JCS golden fixtures -------------------------------------------------


class JcsGoldenFixtures(Assertions):
    def fixtures(self):
        paths = sorted((FIXTURES / "jcs").glob("*.json"))
        self.assertTrue(paths, "no JCS fixtures found")
        return [(path, pluginlib.load_fixture(path)) for path in paths]

    def test_every_fixture_canonicalizes_to_its_golden_bytes(self):
        checked = 0
        for path, fixture in self.fixtures():
            if "error" in fixture:
                continue
            with self.subTest(fixture=path.name):
                value = pluginlib.json_loads_strict(fixture["input_json"])
                self.assertEqual(pluginlib.jcs_dumps(value), fixture["expected"])
                digest = pluginlib.hashlib.sha256(pluginlib.jcs_bytes(value)).hexdigest()
                self.assertEqual(digest, fixture["expected_sha256"])
                checked += 1
        self.assertGreaterEqual(checked, 7)

    def test_refusal_fixtures_raise_before_canonicalization(self):
        checked = 0
        for path, fixture in self.fixtures():
            if "error" not in fixture:
                continue
            with self.subTest(fixture=path.name):
                with self.assertRaises(pluginlib.JcsError) as caught:
                    pluginlib.json_loads_strict(fixture["input_json"])
                self.assertIn(fixture["error"], str(caught.exception))
                checked += 1
        self.assertGreaterEqual(checked, 2)

    def test_descriptor_fixture_pins_descriptor_sha256(self):
        fixture = pluginlib.load_fixture(FIXTURES / "jcs" / "descriptor.json")
        parts = fixture["descriptor_parts"]
        digest = pluginlib.descriptor_sha256(
            parts["name"], parts["parameters"], parts["output_schema"], parts["upstream_annotations"]
        )
        self.assertEqual(digest, fixture["expected_sha256"])


class JcsRules(Assertions):
    def test_duplicate_keys_are_refused_at_every_depth(self):
        for text in ('{"a":1,"a":2}', '{"o":{"a":1,"a":2}}', '{"l":[{"a":1,"a":2}]}'):
            with self.assertRaises(pluginlib.JcsError):
                pluginlib.json_loads_strict(text)

    def test_manifest_loading_refuses_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / PLUGIN
            plugin_dir.mkdir()
            (plugin_dir / "plugin.json").write_text('{"name":"acme","name":"other"}')
            with self.assertRaisesRegex(pluginlib.ValidationError, "duplicate object key"):
                pluginlib.load_manifest(plugin_dir)

    def test_keys_sort_by_utf16_code_unit_not_code_point(self):
        # U+1F600 is a surrogate pair (D83D DE00) so it sorts BEFORE U+E000.
        self.assertEqual(pluginlib.jcs_dumps({"\ue000": 1, "\U0001f600": 2}), '{"\U0001f600":2,"\ue000":1}')

    def test_numbers_follow_ecmascript_tostring(self):
        cases = {
            1: "1",
            1.0: "1",
            -0.0: "0",
            100.0: "100",
            1e16: "10000000000000000",
            1e21: "1e+21",
            1e-6: "0.000001",
            1e-7: "1e-7",
            0.1: "0.1",
            -1.5: "-1.5",
            123.456: "123.456",
        }
        for value, expected in cases.items():
            self.assertEqual(pluginlib.jcs_dumps(value), expected, f"{value!r}")

    def test_unrepresentable_numbers_are_refused(self):
        for value in (float("nan"), float("inf"), 2**53, -(2**53)):
            with self.assertRaises(pluginlib.JcsError):
                pluginlib.jcs_dumps(value)

    def test_del_is_literal_and_control_chars_are_escaped(self):
        self.assertEqual(pluginlib.jcs_dumps("\u007f"), '"\u007f"')
        self.assertEqual(pluginlib.jcs_dumps("\u0000\u001f"), '"\\u0000\\u001f"')


# --- 12. tree_digest_v2 ------------------------------------------------------


class TreeDigestV2(Assertions):
    def fixtures(self):
        paths = sorted((FIXTURES / "tree_digest").glob("*.json"))
        self.assertTrue(paths, "no tree-digest fixtures found")
        return [(path, pluginlib.load_fixture(path)) for path in paths]

    @staticmethod
    def files_of(fixture):
        return {entry["path"]: pluginlib.b64(entry["content_b64"]) for entry in fixture["files"]}

    def test_every_fixture_matches_in_memory(self):
        for path, fixture in self.fixtures():
            with self.subTest(fixture=path.name):
                digest = pluginlib.tree_digest_v2_of_mapping(self.files_of(fixture))
                self.assertEqual(digest, fixture["expected_sha256"])

    def test_every_realizable_fixture_matches_on_disk(self):
        checked = 0
        for path, fixture in self.fixtures():
            if not fixture.get("filesystem_realizable", True):
                continue
            with self.subTest(fixture=path.name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for rel, content in self.files_of(fixture).items():
                    target = root / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                self.assertEqual(pluginlib.tree_digest_v2(root), fixture["expected_sha256"])
                checked += 1
        self.assertGreaterEqual(checked, 3)

    def test_nfd_and_nfc_paths_agree(self):
        nfc = pluginlib.load_fixture(FIXTURES / "tree_digest" / "unicode_paths.json")
        nfd = pluginlib.load_fixture(FIXTURES / "tree_digest" / "unicode_paths_nfd.json")
        self.assertEqual(nfd["equals_fixture"], "unicode_paths")
        self.assertEqual(nfc["expected_sha256"], nfd["expected_sha256"])

    def test_insertion_order_does_not_change_the_digest(self):
        forward = {"a/b": b"1", "a.b": b"2", "z": b"3"}
        backward = {"z": b"3", "a.b": b"2", "a/b": b"1"}
        self.assertEqual(
            pluginlib.tree_digest_v2_of_mapping(forward), pluginlib.tree_digest_v2_of_mapping(backward)
        )

    def test_prefix_like_paths_are_distinguished(self):
        # The length prefixes are what keep these two trees apart.
        self.assertNotEqual(
            pluginlib.tree_digest_v2_of_mapping({"a": b"", "b": b"x"}),
            pluginlib.tree_digest_v2_of_mapping({"ab": b"x"}),
        )

    def test_content_change_changes_the_digest(self):
        self.assertNotEqual(
            pluginlib.tree_digest_v2_of_mapping({"a": b"x"}),
            pluginlib.tree_digest_v2_of_mapping({"a": b"y"}),
        )

    def test_symlinks_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.txt").write_text("x")
            (root / "link.txt").symlink_to(root / "real.txt")
            with self.assertRaisesRegex(pluginlib.ValidationError, "refuses links"):
                pluginlib.tree_digest_v2(root)

    def test_directories_are_not_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "empty_dir").mkdir()
            (root / "a").write_bytes(b"x")
            self.assertEqual(pluginlib.tree_digest_v2(root), pluginlib.tree_digest_v2_of_mapping({"a": b"x"}))


# --- 13. remote data-only content boundary -----------------------------------


class RemoteContentBoundary(TempPlugin):
    def test_local_boundary_is_unchanged(self):
        self.assert_clean(pluginlib.check_boundary(["plugin.json", "src", "bin", "package.json"], has_runtime=True))
        self.assert_error(
            pluginlib.check_boundary(["plugin.json", "package.json"], has_runtime=False), "content-boundary allowlist"
        )

    def test_remote_boundary_allows_data_only(self):
        entries = ["plugin.json", "README.md", "CHANGELOG.md", "LICENSE", "assets", "skills", "yanked.json"]
        self.assert_clean(pluginlib.check_boundary(entries, has_runtime=True, remote=True))

    def test_remote_boundary_refuses_code_and_ecosystem_files(self):
        for entry in ("src", "bin", "package.json", "requirements.txt", "mix.exs", "uv.lock"):
            errors = pluginlib.check_boundary(["plugin.json", entry], has_runtime=True, remote=True)
            self.assert_error(errors, f"top-level entry {entry!r} violates the content-boundary allowlist")

    def test_remote_archive_listing_refuses_code_and_nested_ecosystem_files(self):
        listing = ["./", "./plugin.json", "./src/", "./src/index.js"]
        self.assert_error(
            pluginlib.check_archive_listing(listing, has_runtime=True, remote=True), "top-level entry 'src'"
        )
        listing = ["./", "./plugin.json", "./assets/", "./assets/package.json"]
        self.assert_error(
            pluginlib.check_archive_listing(listing, has_runtime=True, remote=True), "carries no dependency ecosystem"
        )

    def test_remote_archive_listing_accepts_a_data_only_tree(self):
        listing = ["./", "./plugin.json", "./README.md", "./skills/", "./skills/acme/SKILL.md", "./assets/logo.svg"]
        self.assert_clean(pluginlib.check_archive_listing(listing, has_runtime=True, remote=True))

    def test_executable_file_is_refused_by_mode_bit(self):
        plugin_dir = self.materialize(
            remote_manifest(),
            extra_files={"assets/logo.svg": "<svg/>", "assets/run.sh": "#!/bin/sh\n"},
            mode_bits={"assets/run.sh": 0o755},
        )
        with self.assertRaisesRegex(pluginlib.ValidationError, "must contain no executable file"):
            pluginlib.validate_plugin_dir(plugin_dir)

    def test_non_executable_data_files_pass(self):
        plugin_dir = self.materialize(remote_manifest(), extra_files={"assets/logo.svg": "<svg/>"})
        os.chmod(plugin_dir / "assets" / "logo.svg", 0o644)
        pluginlib.validate_plugin_dir(plugin_dir)

    def test_nested_ecosystem_file_is_refused_on_disk(self):
        plugin_dir = self.materialize(remote_manifest(), extra_files={"assets/package.json": "{}"})
        with self.assertRaisesRegex(pluginlib.ValidationError, "carries no dependency ecosystem file"):
            pluginlib.validate_plugin_dir(plugin_dir)


# --- end-to-end: a valid remote plugin, and the api-2 regressions ------------


class ValidatePluginDirRemote(TempPlugin):
    def test_valid_remote_plugin_validates(self):
        manifest = remote_manifest()
        manifest["skills"] = [{"name": "acme-plugin", "path": "skills/acme-plugin/SKILL.md"}]
        manifest["interface"] = {"short_description": "Use Acme", "developer_name": "Fermix", "logo": "assets/logo.svg"}
        plugin_dir = self.materialize(
            manifest,
            extra_files={
                "skills/acme-plugin/SKILL.md": "# Acme\n",
                "assets/logo.svg": "<svg/>",
                "README.md": "# acme\n",
                "CHANGELOG.md": "# changelog\n",
            },
        )
        self.assertEqual(pluginlib.validate_plugin_dir(plugin_dir)["name"], PLUGIN)
        self.assertTrue(pluginlib.is_remote_manifest(manifest))

    def test_remote_plugin_with_src_is_refused(self):
        plugin_dir = self.materialize(remote_manifest(), extra_files={"src/index.js": "// nope\n"})
        with self.assertRaisesRegex(pluginlib.ValidationError, "top-level entry 'src'"):
            pluginlib.validate_plugin_dir(plugin_dir)

    def test_api2_manifest_with_an_api3_field_is_refused_end_to_end(self):
        plugin_dir = self.materialize(api2_manifest(budgets={"agent_turn_calls": 5, "agent_turn_paginated_calls": 1}))
        with self.assertRaisesRegex(pluginlib.ValidationError, r"budgets requires plugin_api >= 3"):
            pluginlib.validate_plugin_dir(plugin_dir)

    def test_plain_api2_plugin_still_validates(self):
        plugin_dir = self.materialize(api2_manifest())
        self.assertEqual(pluginlib.validate_plugin_dir(plugin_dir)["plugin_api"], 2)

    def test_api2_manifest_is_untouched_by_the_remote_contract(self):
        self.assert_clean(pluginlib._validate_remote_contract(api2_manifest()))


# --- 14. check_plugin_package.py --------------------------------------------


class CheckPluginPackage(TempPlugin):
    def run_script(self, plugin_dir):
        return subprocess.run(
            [sys.executable, str(CHECK_PACKAGE), str(plugin_dir)], capture_output=True, text=True, check=False
        )

    def test_data_only_remote_plugin_packages_cleanly(self):
        plugin_dir = self.materialize(
            remote_manifest(),
            extra_files={"README.md": "# acme\n", "skills/acme-plugin/SKILL.md": "# skill\n"},
        )
        result = self.run_script(plugin_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok: packaged", result.stdout)
        self.assertIn("members", result.stdout)

    def test_remote_plugin_with_code_fails_packaging(self):
        plugin_dir = self.materialize(remote_manifest(), extra_files={"bin/server": "#!/bin/sh\n"})
        result = self.run_script(plugin_dir)
        self.assertEqual(result.returncode, 1)
        self.assertIn("top-level entry 'bin'", result.stderr)

    def test_temp_tarball_is_discarded_on_every_path(self):
        plugin_dir = self.materialize(remote_manifest())
        before = set(Path(tempfile.gettempdir()).glob("fermix-plugin-pack-*"))
        errors, members, packed_bytes = check_plugin_package.check_package(plugin_dir)
        self.assertEqual(errors, [])
        self.assertGreater(members, 0)
        self.assertGreater(packed_bytes, 0)
        after = set(Path(tempfile.gettempdir()).glob("fermix-plugin-pack-*"))
        self.assertEqual(before, after)

    def test_failure_also_discards_the_temp_tarball(self):
        plugin_dir = self.materialize(remote_manifest(), extra_files={"src/x.js": "x\n"})
        before = set(Path(tempfile.gettempdir()).glob("fermix-plugin-pack-*"))
        with self.assertRaises(pluginlib.ValidationError):
            check_plugin_package.check_package(plugin_dir)
        after = set(Path(tempfile.gettempdir()).glob("fermix-plugin-pack-*"))
        self.assertEqual(before, after)


# --- 15. validate_plugin.py draft handling (M27 §12 Stage 0) -----------------


def draft_manifest(**overrides):
    """A remote manifest whose Stage-0-captured fields are still placeholders."""
    manifest = remote_manifest()
    manifest["draft"] = True
    for tool in manifest["tools"]:
        for field in ("parameters", "output_schema", "upstream_annotations", "descriptor_sha256"):
            tool[field] = validate_plugin.DRAFT_SENTINEL
    manifest.update(overrides)
    return manifest


class DraftHandling(TempPlugin):
    """`draft: true` is a manifest STATE, never a relaxed grammar: `--all` skips
    it so one pending capture cannot block every other plugin's CI, naming the
    directory reports exactly which fields are pending, and the release path
    refuses it outright."""

    def materialize_repo(self, manifest):
        """A throwaway repo root holding plugins/<name>/plugin.json."""
        plugin_dir = self.root / "plugins" / manifest["name"]
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest, indent=2))
        return plugin_dir

    def run_validate(self, *argv):
        return subprocess.run(
            [sys.executable, str(VALIDATE), *argv],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(self.root),
        )

    def test_pending_fields_reports_every_sentinel_path_in_document_order(self):
        manifest = {"a": validate_plugin.DRAFT_SENTINEL, "b": [{"c": validate_plugin.DRAFT_SENTINEL}], "d": 1}
        self.assertEqual(validate_plugin.pending_fields(manifest), ["/a", "/b/0/c"])

    def test_pending_fields_is_empty_for_a_captured_manifest(self):
        self.assertEqual(validate_plugin.pending_fields(remote_manifest()), [])

    def test_all_skips_a_draft_and_exits_zero(self):
        self.materialize_repo(draft_manifest())
        result = self.run_validate("--all")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SKIPPED (draft — Stage 0 capture pending)", result.stdout)

    def test_all_still_fails_a_non_draft_plugin(self):
        self.materialize_repo(remote_manifest(version="not-semver"))
        result = self.run_validate("--all")
        self.assertEqual(result.returncode, 1)
        self.assertIn("version must be semver", result.stderr)

    def test_all_passes_a_captured_plugin(self):
        self.materialize_repo(remote_manifest())
        result = self.run_validate("--all")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok: plugins/acme", result.stdout)

    def test_naming_a_draft_runs_the_full_grammar_and_lists_pending_fields(self):
        self.materialize_repo(draft_manifest())
        result = self.run_validate("plugins/acme")
        self.assertEqual(result.returncode, 1)
        self.assertIn("DRAFT — Stage 0 authenticated capture pending", result.stderr)
        self.assertIn("pending: /tools/0/parameters", result.stderr)
        self.assertIn("pending: /tools/0/descriptor_sha256", result.stderr)
        # The grammar is not relaxed for a draft: it still reports the placeholders.
        self.assertIn("descriptor_sha256 must be 64 lowercase hex characters", result.stderr)

    def test_release_path_refuses_a_draft_before_reading_the_listing(self):
        self.materialize_repo(draft_manifest())
        listing = self.root / "listing.txt"
        listing.write_text("./\n./plugin.json\n")
        result = self.run_validate("--archive", "listing.txt", "plugins/acme")
        self.assertEqual(result.returncode, 1)
        self.assertIn("refusing to release a draft manifest", result.stderr)

    def test_a_draft_with_nothing_pending_is_an_error_not_a_skip(self):
        self.materialize_repo(remote_manifest(draft=True))
        result = self.run_validate("--all")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no STAGE0_PENDING placeholder remains", result.stderr)
        self.assertNotIn("SKIPPED", result.stdout)


if __name__ == "__main__":
    unittest.main()
