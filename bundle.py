"""Bundle setup, imported skill aliases, and read-only command diagnostics."""

from functools import partial
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent


def defaults():
    return json.loads((ROOT / 'plugins/defaults.json').read_text(encoding='utf-8'))


def record_skill_repository(home, source, names):
    """Record expected imports before installation so partial setup stays visible."""
    path = Path(home) / '.toolset-imports.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    state[source] = sorted(names)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.replace(path)


def missing_skill_imports(home, command_names):
    path = Path(home) / '.toolset-imports.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    expected = set(defaults()['required_skills'])
    missing_sources = []
    for line in (ROOT / 'plugins/PLUGINS.md').read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == 'skills':
            if fields[1] not in state:
                missing_sources.append(fields[1])
            expected.update(state.get(fields[1], []))
    return sorted(expected - command_names), missing_sources


def _alias(name):
    name = re.sub(r'[^a-z0-9-]', '-', name.lower().replace('_', '-')).strip('-')
    if len(name) > 32:
        name = name[:23] + '-' + hashlib.sha256(name.encode()).hexdigest()[:8]
    return name


def register_imported_skills(ctx, invoke):
    from hermes_cli.commands import resolve_command
    from hermes_cli.plugins import get_plugin_commands, get_plugin_manager

    manager = get_plugin_manager()
    commands = get_plugin_commands()
    allowed = defaults()['imported_plugins']
    aliases = {}
    for info in manager.list_plugin_skill_metadata():
        namespace, sep, name = info['name'].partition(':')
        if not sep or namespace not in allowed:
            continue
        if info.get('frontmatter', {}).get('user-invocable') is False:
            continue
        command = _alias(name)
        # Keep an upstream native command when it already implements this skill.
        if command in commands and commands[command].get('plugin') == namespace:
            continue
        if not command or resolve_command(command) is not None or command in commands:
            command = _alias(f'{namespace}-{name}')
        if not command or resolve_command(command) is not None or command in commands:
            continue
        path = manager.find_plugin_skill(info['name'])
        if path is None or not path.is_file():
            continue
        ctx.register_command(command, partial(invoke, ctx, name, path, namespace=namespace),
                             description=f"Run {info['name']}", args_hint='[instructions]')
        aliases[command] = info['name']
    return aliases


def inventory():
    from hermes_cli.plugins import get_plugin_commands, get_plugin_manager
    from hermes_cli.commands_platforms import telegram_menu_commands, telegram_menu_max_commands
    from agent.skill_commands import get_skill_commands

    manager = get_plugin_manager()
    manager.discover_and_load()
    plugins = manager.list_plugins()
    wanted = set(defaults()['imported_plugins']) | {'hermes-toolset'}
    rows = []
    for name, item in sorted(get_plugin_commands().items()):
        if item.get('plugin') in wanted:
            rows.append({'command': name, 'telegram': name.replace('-', '_'),
                         'source': item['plugin'], 'kind': 'plugin'})
    for name, item in sorted(get_skill_commands().items()):
        name = name.lstrip('/')
        rows.append({'command': name, 'telegram': name.replace('-', '_'),
                     'source': item.get('name', name), 'kind': 'skill'})
    menu_limit = telegram_menu_max_commands()
    menu, hidden = telegram_menu_commands(max_commands=menu_limit)
    menu_names = dict(menu)
    for row in rows:
        row['in_telegram_menu'] = row['telegram'] in menu_names
    selected = [p for p in plugins if p['name'] in wanted]
    loaded = {p['name'] for p in selected if p.get('enabled') and not p.get('error')}
    required = wanted
    missing_skills, unchecked_sources = missing_skill_imports(
        manager.home_path, {row['command'] for row in rows})
    return {'plugins': selected, 'missing_plugins': sorted(required - loaded),
            'plugin_skills': sorted(info['name'] for info in manager.list_plugin_skill_metadata()
                                    if info['name'].partition(':')[0] in wanted),
            'missing_skills': missing_skills, 'unchecked_skill_sources': unchecked_sources,
            'commands': rows, 'telegram_menu_hidden': hidden, 'telegram_menu_limit': menu_limit,
            'note': 'Menu capacity is limited; typed commands and /toolset list remain available.'}


def list_commands(raw_args=''):
    report = inventory()
    request = raw_args.strip().lower()
    query = request[5:].strip() if request.startswith('list ') else ('' if request == 'list' else request)
    rows = [r for r in report['commands'] if not query or query in r['command'] or query in r['source']]
    if request:
        lines = [f'Toolset commands: {len(rows)} matches']
        for row in rows:
            alias = f" (Telegram: /{row['telegram']})" if row['telegram'] != row['command'] else ''
            lines.append(f"/{row['command']}{alias} — {row['source']}")
    else:
        lines = ['Hermes toolset bundle']
        for plugin in report['plugins']:
            name = plugin['name']
            version = f" {plugin['version']}" if plugin.get('version') else ''
            status = 'error' if plugin.get('error') else ('loaded' if plugin.get('enabled') else 'disabled')
            skills = sum(n.startswith(name + ':') for n in report['plugin_skills'])
            lines.append(f"{name}{version}: {status} — {plugin.get('tools', 0)} tools, "
                         f"{plugin.get('commands', 0)} commands, {skills} skills, {plugin.get('hooks', 0)} hooks")
        lines += [f"{len(report['commands'])} available commands across plugins and local/external skills.",
                  'Per-plugin skill counts cover registered plugin skills; OMH workflow skills are loaded separately.',
                  'Counts show registered capabilities, not tools enabled in your current chat.',
                  '/toolsets lists tool groups; plugins can provide skills, commands and hooks without a tool group.']
    if report['missing_plugins']:
        lines.append('Missing/disabled plugins: ' + ', '.join(report['missing_plugins']))
    lines.extend(f"{p['name']}: {p['error']}" for p in report['plugins'] if p.get('error'))
    if report['missing_skills']:
        lines.append('Unavailable skill commands (missing, blocked, or ambiguous): ' + ', '.join(report['missing_skills']))
    if report['unchecked_skill_sources']:
        lines.append('Skill repositories not yet set up: ' + ', '.join(report['unchecked_skill_sources']))
    if report['telegram_menu_hidden']:
        lines.append('Telegram menu capacity hides some entries; type their commands directly.')
    lines.append('Commands: /toolset list · Filter: /toolset ponytail')
    lines.append('Diagnostics: hermes toolset doctor --json · Setup: hermes toolset setup')
    return '\n'.join(lines)


def setup_parser(parser):
    actions = parser.add_subparsers(dest='action', required=True)
    setup = actions.add_parser('setup', help='Install, enable, and configure sources in plugins/PLUGINS.md')
    setup.add_argument('--dry-run', action='store_true')
    setup.add_argument('--hermes-home', help='Hermes root containing profiles/')
    setup.add_argument('--yes-deps', action='store_true', help='Consent to declared Python dependencies')
    doctor = actions.add_parser('doctor', help='Report enabled plugins and available commands')
    doctor.add_argument('--json', action='store_true')


def handle_cli(args):
    if args.action == 'doctor':
        report = inventory()
        print(json.dumps(report, indent=2) if args.json else list_commands())
        return int(bool(report['missing_plugins'] or report['missing_skills'] or report['unchecked_skill_sources']))
    argv = ['bash', str(ROOT / 'install-plugins.sh'), '--enable', '--setup']
    if args.dry_run:
        argv.append('--dry-run')
    if args.hermes_home:
        argv += ['--hermes-home', args.hermes_home]
    if args.yes_deps:
        argv.append('--yes-deps')
    return subprocess.run(argv, check=False).returncode


def register_bundle(ctx, invoke):
    register_imported_skills(ctx, invoke)
    ctx.register_command('toolset', list_commands, description='Bundle status, missing imports, and command inventory',
                         args_hint='[list|filter]')
    ctx.register_cli_command('toolset', help='Install and diagnose the Hermes toolset bundle',
                             setup_fn=setup_parser, handler_fn=handle_cli)
