"""Verify an installed bundle using Hermes' Python, without bot or model calls.

Set HERMES_HOME to an isolated installed profile. This checks actual loaders,
skill content, CLI queues and captured gateway routing. Missing imports fail.
"""

import json
from pathlib import Path
from queue import Queue
from types import SimpleNamespace


def main():
    from hermes_cli.plugins import get_plugin_manager, get_plugin_commands
    from agent.skill_commands import get_skill_commands, build_skill_invocation_message, resolve_skill_command_key
    from gateway.session_context import set_session_vars, clear_session_vars
    from tools.skills_tool import skill_view

    manager = get_plugin_manager()
    manager.discover_and_load()
    commands = get_plugin_commands()
    assert 'toolset' in commands, 'hermes-toolset did not load'
    # The command's globals belong to the actual loaded bundle module.
    report = commands['toolset']['handler'].__globals__['inventory']()
    checked_skills = 0
    for name, info in get_skill_commands().items():
        assert resolve_skill_command_key(name.lstrip('/').replace('-', '_')) == name, name
        assert build_skill_invocation_message(name, 'integration probe'), name
        checked_skills += 1
    for info in manager.list_plugin_skill_metadata():
        result = json.loads(skill_view(info['name']))
        assert 'error' not in result, (info['name'], result)
        checked_skills += 1

    cli = SimpleNamespace(_pending_input=Queue(), _agent_running=False)
    accepted = []
    owner = object()
    manager.set_gateway_message_injector(owner, lambda **kw: accepted.append(kw) or True)
    checked_aliases = 0
    try:
        for name, info in commands.items():
            if info.get('plugin') != 'hermes-toolset' or name == 'toolset':
                continue
            manager._cli_ref = cli
            tokens = set_session_vars()
            try:
                assert info['handler']('integration probe') is None, name
                message = cli._pending_input.get_nowait()
                assert 'skill_view(' in message and 'integration probe' in message, name
            finally:
                clear_session_vars(tokens)
                manager._cli_ref = None
            tokens = set_session_vars(platform='telegram', chat_id='-10042',
                                      chat_type='group', thread_id='99', user_id='123')
            try:
                assert info['handler']('integration probe') is None, name
                assert accepted[-1]['origin']['thread_id'] == '99', name
                assert accepted[-1]['plugin_home'] == manager.home_path, name
            finally:
                clear_session_vars(tokens)
            checked_aliases += 1
    finally:
        manager._cli_ref = None
        manager.clear_gateway_message_injector(owner)
    summary = {
        'checked_skill_content': checked_skills,
        'checked_cli_and_gateway_aliases': checked_aliases,
        'command_count': len(report['commands']),
        'plugin_commands': {p['name']: p['commands'] for p in report['plugins']},
        'plugin_tools': {p['name']: p['tools'] for p in report['plugins']},
        'missing_plugins': report['missing_plugins'],
        'missing_skills': report['missing_skills'],
        'unchecked_skill_sources': report['unchecked_skill_sources'],
    }
    print(json.dumps(summary, indent=2))
    return int(bool(report['missing_plugins'] or report['missing_skills'] or report['unchecked_skill_sources']))


if __name__ == '__main__':
    raise SystemExit(main())
