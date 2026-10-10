"""Offline plugin contracts; Hermes itself is checked separately at integration time."""

import importlib.util
from pathlib import Path
import tempfile
import types
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class Context:
    def __init__(self):
        self.skills = {}
        self.commands = {}
        self.messages = []
        self.accept = True

    def register_skill(self, name, path):
        self.skills[name] = path

    def register_command(self, name, handler, description="", args_hint=""):
        self.commands[name] = handler

    def register_cli_command(self, *args, **kwargs):
        pass

    def get_config(self, key, default=None):
        return default

    def inject_message(self, content, **kwargs):
        self.messages.append((content, kwargs))
        return self.accept


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / "__init__.py").is_file(), "Missing plugin entry point")
        spec = importlib.util.spec_from_file_location("toolset_under_test", ROOT / "__init__.py")
        self.plugin = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.plugin
        spec.loader.exec_module(self.plugin)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plugin.SKILLS_DIR = self.root
        self.session = {}
        self.existing = {}
        modules = {
            "gateway.session_context": types.SimpleNamespace(
                get_session_env=lambda name, default="": self.session.get(name, default)),
            "hermes_cli.commands": types.SimpleNamespace(
                resolve_command=lambda name: object() if name == "help" else None),
            "hermes_cli.plugins": types.SimpleNamespace(
                get_plugin_commands=lambda: self.existing,
                get_plugin_manager=lambda: types.SimpleNamespace(list_plugin_skill_metadata=lambda: [])),
        }
        mock_modules = patch.dict("sys.modules", modules)
        mock_modules.start()
        self.addCleanup(mock_modules.stop)
        self.ctx = Context()

    def skill(self, name):
        folder = self.root / name
        folder.mkdir(parents=True)
        path = folder / "SKILL.md"
        path.write_text("---\nname: " + name + "\ndescription: Test skill\n---\nDo the work.\n")
        return path

    def test_discovers_new_skills_on_next_registration(self):
        self.skill("alpha")
        (self.root / "not-a-skill").mkdir()
        self.plugin.register(self.ctx)
        self.assertEqual(set(self.ctx.commands), {"alpha", "toolset"})
        self.skill("beta")
        next_ctx = Context()
        self.plugin.register(next_ctx)
        self.assertEqual(set(next_ctx.commands), {"alpha", "beta", "toolset"})

    def test_each_handler_loads_its_own_namespaced_skill_and_preserves_arguments(self):
        alpha = self.skill("alpha")
        self.skill("beta")
        self.plugin.register(self.ctx)
        self.assertEqual(self.ctx.skills["alpha"], alpha)
        args = 'only src/; $(touch /tmp/should-not-run)\nno push'
        self.assertIsNone(self.ctx.commands["alpha"](args))
        message, target = self.ctx.messages[-1]
        self.assertIn('skill_view(name="hermes-toolset:alpha")', message)
        self.assertIn(args, message)
        self.assertNotIn("hermes-toolset:beta", message)
        self.assertEqual(target, {})

    def test_gateway_routes_first_command_to_origin_including_topic_and_user(self):
        self.skill("git-commit-push")
        self.plugin.register(self.ctx)
        self.session.update({
            "HERMES_SESSION_PLATFORM": "telegram", "HERMES_SESSION_CHAT_ID": "-10042",
            "HERMES_SESSION_THREAD_ID": "99", "HERMES_SESSION_USER_ID": "123",
            "HERMES_SESSION_CHAT_TYPE": "group", "HERMES_SESSION_PROFILE": "dev",
        })
        self.ctx.commands["git-commit-push"]("no push")
        origin = self.ctx.messages[-1][1]["origin"]
        self.assertEqual(origin["platform"], "telegram")
        self.assertEqual(origin["chat_id"], "-10042")
        self.assertEqual(origin["thread_id"], "99")
        self.assertEqual(origin["user_id"], "123")
        self.assertEqual(origin["profile"], "dev")

    def test_injection_rejection_explains_required_setting(self):
        self.skill("alpha")
        self.plugin.register(self.ctx)
        self.ctx.accept = False
        result = self.ctx.commands["alpha"]("")
        self.assertIn("allow_gateway_injection", result)
        self.assertIn("not started", result)

    def test_removed_skill_is_not_queued(self):
        path = self.skill("alpha")
        self.plugin.register(self.ctx)
        path.unlink()
        self.assertIn("no longer exists", self.ctx.commands["alpha"](""))
        self.assertEqual(self.ctx.messages, [])

    def test_builtin_and_existing_plugin_commands_are_not_overwritten(self):
        self.skill("help")
        self.skill("alpha")
        self.existing["alpha"] = {"plugin": "other"}
        with self.assertLogs(level="WARNING"):
            self.plugin.register(self.ctx)
        self.assertEqual(set(self.ctx.commands), {"toolset"})
        self.assertEqual(set(self.ctx.skills), {"help", "alpha"})

    def test_invalid_names_and_telegram_alias_collisions_fail_before_registration(self):
        for names in (("bad.name",), ("a" * 33,), ("a-b", "a_b")):
            with self.subTest(names=names):
                with tempfile.TemporaryDirectory() as directory:
                    self.root = Path(directory)
                    self.plugin.SKILLS_DIR = self.root
                    for name in names:
                        self.skill(name)
                    ctx = Context()
                    with self.assertRaises(ValueError):
                        self.plugin.register(ctx)
                    self.assertEqual(ctx.skills, {})
                    self.assertEqual(ctx.commands, {})

    def test_symlink_outside_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "SKILL.md"
            path.write_text("Outside")
            (self.root / "escape").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.plugin.register(self.ctx)

    def test_repository_skills_are_all_discovered(self):
        self.plugin.SKILLS_DIR = ROOT / "skills"
        self.plugin.register(self.ctx)
        self.assertTrue({"autogoal", "git-commit-push", "git-pull-merge", "lgtm", "repo-docs"}
                        <= set(self.ctx.commands))


if __name__ == "__main__":
    unittest.main()
