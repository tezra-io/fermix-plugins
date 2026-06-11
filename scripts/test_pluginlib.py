#!/usr/bin/env python3
"""Unit tests for the publish-side validation boundary in pluginlib.

Focus: a manifest must not be able to point skills/interface assets outside the
plugin directory, and runtime.command must be a bare executable name. These
mirror the core decoder's install-time guards; keep them in sync.

Run: python3 scripts/test_pluginlib.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pluginlib  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
