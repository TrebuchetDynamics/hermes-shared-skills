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
            "    hermes-toolset:\n      allow_gateway_injection: true\n"
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
        manager.discover_and_load()
        loaded = manager._plugins["hermes-toolset"]
        assert loaded.enabled and not loaded.error, loaded.error
        commands = get_plugin_commands()
        assert {"autogoal", "git-commit-push", "git-pull-merge", "lgtm", "repo-docs"} <= commands.keys()
        assert manager.find_plugin_skill("hermes-toolset:repo-docs") == root / "skills/repo-docs/SKILL.md"
        payload = json.loads(skill_view("hermes-toolset:repo-docs"))
        assert "error" not in payload, payload

        menu, _ = telegram_menu_commands()
        assert "git_commit_push" in dict(menu), menu
        assert "repo_docs" in dict(menu), menu

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
        print("PASS: manifest, real loader, skill_view, Telegram menu, CLI queue, gateway routing, unload")


if __name__ == "__main__":
    main()
