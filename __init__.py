"""Discover bundled skills and expose them through Hermes' command API."""

from functools import partial
import logging
from pathlib import Path
import re


SKILLS_DIR = Path(__file__).resolve().parent / "skills"
logger = logging.getLogger(__name__)
_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}\Z")


def _discover_skills():
    """Validate the complete command set before registering anything."""
    root = SKILLS_DIR.resolve()
    skills = []
    commands = set()
    for folder in sorted(root.iterdir()):
        path = folder / "SKILL.md"
        if not folder.is_dir() or not path.is_file():
            continue
        name = folder.name
        if not _NAME.fullmatch(name):
            raise ValueError(f"Invalid skill folder {name!r}: use 1–32 lowercase letters, digits, '-' or '_'.")
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Skill {name!r} points outside the bundled skills directory.")
        # Hermes maps Telegram underscores back to hyphens at dispatch time.
        command = name.replace("_", "-")
        if command in commands:
            raise ValueError(f"Skills collide on command /{command} after Telegram normalization.")
        commands.add(command)
        skills.append((name, command, path))
    return skills


def _invoke(ctx, name, path, raw_args, namespace="hermes-toolset"):
    from gateway.session_context import get_session_env

    if not path.is_file():
        return f"Skill {name!r} no longer exists. Update the plugin and restart Hermes."
    prompt = (
        f"The user invoked the /{name} skill command. "
        f'Load skill_view(name="{namespace}:{name}") and follow its instructions '
        "to perform the requested work in this conversation. "
        "Resolve supporting files relative to that skill's directory.\n\n"
        f"User arguments:\n{raw_args}"
    )
    platform = get_session_env("HERMES_SESSION_PLATFORM")
    chat_id = get_session_env("HERMES_SESSION_CHAT_ID")
    target = {}
    if platform and chat_id:
        # Origin routing also works when this is the first message in a chat.
        # Hermes retains profile ownership and applies gateway admission rules.
        origin = {"platform": platform, "chat_id": chat_id}
        for field in ("chat_type", "chat_name", "thread_id", "user_id", "user_id_alt",
                      "user_name", "scope_id", "parent_chat_id", "message_id", "profile"):
            value = get_session_env(f"HERMES_SESSION_{field.upper()}")
            if value:
                origin[field] = value
        target["origin"] = origin
    elif session_key := get_session_env("HERMES_SESSION_KEY"):
        target["session_key"] = session_key
    if ctx.inject_message(prompt, **target):
        return None
    return (
        f"Skill {name!r} was not started. For Telegram/gateway use, set "
        "plugins.entries.hermes-toolset.allow_gateway_injection: true in this profile's "
        "config.yaml and restart its gateway. If already enabled, check Hermes gateway logs."
    )


def register(ctx):
    """Hermes plugin entry point; called again on plugin load after a restart."""
    from hermes_cli.commands import resolve_command
    from hermes_cli.plugins import get_plugin_commands

    skills = _discover_skills()
    from .runtime_defaults import apply_runtime_defaults
    apply_runtime_defaults(ctx)
    existing = get_plugin_commands()
    for name, command, path in skills:
        ctx.register_skill(name, path)
        if resolve_command(command) is not None or command in existing:
            logger.warning("Skipping /%s: command already exists; use skill_view('hermes-toolset:%s').",
                           command, name)
            continue
        ctx.register_command(
            command, partial(_invoke, ctx, name, path),
            description=f"Run the {name} skill", args_hint="[instructions]",
        )
    from .bundle import register_bundle
    register_bundle(ctx, _invoke)
