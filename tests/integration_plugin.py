"""Run with Hermes' Python and its source root on PYTHONPATH; no bot or LLM calls."""

import os
from pathlib import Path
from queue import Queue
import tempfile
from types import SimpleNamespace


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="hermes-toolset-test-") as directory:
        home = Path(directory)
        os.environ["HERMES_HOME"] = str(home)
        os.environ.pop("HERMES_SAFE_MODE", None)
        (home / "plugins").mkdir()
        (home / "plugins" / "hermes-toolset").symlink_to(root, target_is_directory=True)
        (home / "config.yaml").write_text(
            "plugins:\n  enabled: [hermes-toolset]\n  entries:\n"
            "    hermes-toolset:\n      allow_gateway_injection: false\n"
            "approvals:\n  mode: manual\n  destructive_slash_confirm: true\n"
            "  mcp_reload_confirm: true\n  deny: ['keep-this-deny-rule']\n"
            "model:\n  default: keep-this-model\n"
        )

        from hermes_cli.plugins_cmd_install import _read_manifest_for_install
        from hermes_cli.plugins import get_plugin_manager, get_plugin_commands
        from hermes_cli.commands_platforms import telegram_menu_commands
        from gateway.session_context import set_session_vars, clear_session_vars
        from tools.skills_tool import skill_view
        import json

        manifest = _read_manifest_for_install(root)
        assert manifest["name"] == "hermes-toolset", manifest
        manager = get_plugin_manager()
        # A shared gateway can have another profile current at discovery time.
        from hermes_constants import set_hermes_home_override, reset_hermes_home_override
        other = home / 'other-profile'
        other.mkdir()
        other_config = other / 'config.yaml'
        other_config.write_text('approvals:\n  mode: manual\n')
        other_before = other_config.read_bytes()
        token = set_hermes_home_override(other)
        try:
            manager.discover_and_load()
        finally:
            reset_hermes_home_override(token)
        assert other_config.read_bytes() == other_before
        loaded = manager._plugins["hermes-toolset"]
        assert loaded.enabled and not loaded.error, loaded.error
        from hermes_cli.config import require_readable_config_before_write
        configured = require_readable_config_before_write()
        assert configured['approvals']['destructive_slash_confirm'] is False, configured['approvals']
        assert configured['approvals']['mcp_reload_confirm'] is False
        assert configured['approvals']['mode'] == 'off'
        assert configured['approvals']['deny'] == ['keep-this-deny-rule']
        assert configured['model']['default'] == 'keep-this-model'
        assert configured['plugins']['entries']['hermes-toolset']['allow_gateway_injection'] is True

        from hermes_cli.plugins import PluginContext
        from hermes_cli.config import save_config
        from importlib import import_module
        policy = import_module(loaded.module.__name__ + '.runtime_defaults')
        ctx = PluginContext(loaded.manifest, manager)
        config_path = home / 'config.yaml'
        before = (config_path.read_bytes(), config_path.stat().st_mtime_ns)
        policy.apply_runtime_defaults(ctx)
        assert (config_path.read_bytes(), config_path.stat().st_mtime_ns) == before
        save_config({'plugins': {'entries': {'hermes-toolset': {'settings': {
            'apply_runtime_defaults': False}}}}, 'approvals': {'destructive_slash_confirm': True}},
            merge_existing=True)
        before = config_path.read_bytes()
        policy.apply_runtime_defaults(ctx)
        assert config_path.read_bytes() == before
        save_config({'plugins': {'entries': {'hermes-toolset': {'settings': {
            'apply_runtime_defaults': True}}}}}, merge_existing=True)
        policy.apply_runtime_defaults(ctx)
        configured = require_readable_config_before_write()
        assert configured['approvals']['destructive_slash_confirm'] is False

        # Exercise the actual /new gate with a harmless callback, never reset a session.
        import asyncio
        from gateway.run_busy import GatewayBusySessionMixin
        called = []
        async def execute():
            called.append(True)
            return 'executed'
        runner = SimpleNamespace(_read_user_config=lambda: configured)
        result = asyncio.run(GatewayBusySessionMixin._maybe_confirm_destructive_slash(
            runner, event=None, command='new', title='New', detail='test', execute=execute))
        assert result == 'executed' and called == [True]
        commands = get_plugin_commands()
        assert {"autogoal", "git-commit-push", "git-pull-merge", "lgtm", "repo-docs", "repo-interview"} <= commands.keys()
        assert manager.find_plugin_skill("hermes-toolset:repo-docs") == root / "skills/repo-docs/SKILL.md"
        payload = json.loads(skill_view("hermes-toolset:repo-docs"))
        assert "error" not in payload, payload

        menu, _ = telegram_menu_commands()
        assert "git_commit_push" in dict(menu), menu
        assert "repo_docs" in dict(menu), menu
        assert "repo_interview" in dict(menu), menu
        interview = json.loads(skill_view("hermes-toolset:repo-interview"))
        assert "error" not in interview, interview

        cli = SimpleNamespace(_pending_input=Queue(), _agent_running=False)
        manager._cli_ref = cli
        tokens = set_session_vars()
        try:
            assert commands["repo-docs"]["handler"]("update the README") is None
            queued = cli._pending_input.get_nowait()
            assert 'skill_view(name="hermes-toolset:repo-docs")' in queued
            assert "update the README" in queued
        finally:
            clear_session_vars(tokens)
            manager._cli_ref = None

        accepted = []
        manager.set_gateway_message_injector(accepted, lambda **kwargs: accepted.append(kwargs) or True)
        tokens = set_session_vars(platform="telegram", chat_id="-10042", chat_type="group",
                                  thread_id="99", user_id="123", profile="dev")
        try:
            assert commands["git-commit-push"]["handler"]("no push") is None
            assert accepted[-1]["origin"]["thread_id"] == "99", accepted
            assert accepted[-1]["origin"]["user_id"] == "123", accepted
            assert accepted[-1]["plugin_home"] == home, accepted
        finally:
            clear_session_vars(tokens)
        manager.unload("hermes-toolset")
        assert "repo-docs" not in manager._plugin_commands
        assert manager.find_plugin_skill("hermes-toolset:repo-docs") is None
        # Broken YAML must remain recoverable, never replaced by fallback defaults.
        config_path.write_text('approvals: [broken')
        before = config_path.read_bytes()
        try:
            policy.apply_runtime_defaults(SimpleNamespace(get_config=lambda key, default: default))
        except RuntimeError:
            pass
        else:
            raise AssertionError('Malformed configuration was accepted')
        assert config_path.read_bytes() == before
        print("PASS: loader approval defaults, /new gate, profile isolation, idempotency, opt-out, "
              "malformed YAML, skill_view, Telegram menu, CLI queue, gateway routing, unload")


if __name__ == "__main__":
    main()
