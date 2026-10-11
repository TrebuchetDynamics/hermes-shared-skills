# hermes-toolset

A Hermes plugin that turns the skills in this repository into commands in
Hermes CLI chat and Telegram. Add a `skills/<name>/SKILL.md`, update the installed
plugin, and restart Hermes; there is no command list to maintain.

## Install

For a published version that includes `hermes toolset setup`:

Setup is broader than installing this plugin: the current source inventory targets
all profiles for OMH, Bot Forge, Ponytail, external skills, Graphify, speech support,
and Hindsight memory. On first setup, choose a Hindsight backend as described
below and pass its connection JSON with `--hindsight-config`. If the published version
does not yet include setup, use the local checkout instructions below.

```sh
hermes plugins install TrebuchetDynamics/hermes-toolset
hermes plugins enable hermes-toolset
hermes toolset setup --yes-deps --hindsight-config /path/to/connection.json
hermes toolset doctor
```

For local development, link this checkout into your profile's plugin directory.
Run from the repository root (this fails safely if the target already exists):

```sh
python - <<'PY'
import os
from pathlib import Path
home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
plugins = home / "plugins"
plugins.mkdir(parents=True, exist_ok=True)
(plugins / "hermes-toolset").symlink_to(Path.cwd(), target_is_directory=True)
PY
hermes plugins enable hermes-toolset
```

Plugins are enabled per profile. For a named profile, use that profile's home for
the link and `hermes -p PROFILE plugins enable hermes-toolset` to enable it.
`hermes toolset setup` installs and enables the sources in
[plugins/PLUGINS.md](plugins/PLUGINS.md), including external skill repositories,
Graphify's Hermes integration, OMH's full setup, and Hindsight memory setup. It also links and enables
hermes-toolset itself in every existing live profile, preserving existing plugin
installations. After creating another profile, rerun setup or, from this checkout,
run `bash install-plugins.sh --bundle-only` to add just this bundle and its defaults
across profiles. The links depend on keeping this checkout installed. It applies
[our defaults](plugins/defaults.json): preserve OMH's existing store, keep the
current TUI, disable the optional menubar, allow toolset gateway injection, and
set `approvals.mode` to `off` for profiles with hermes-toolset installed. This
disables terminal command approval prompts throughout those profiles, including
CLI and messaging sessions. The plugin itself applies these approval and gateway
injection defaults whenever it loads, including disabling `/new`, `/clear`,
`/reset`, `/undo` and MCP-reload confirmations. No setup command is needed for
this policy after the plugin is enabled. It writes only when values differ and
preserves other settings, including explicit deny rules. Hermes hard blocks still
apply. Setup also clears global and per-channel skill disable lists.
To opt out of automatic policy application, first run
`hermes -p PROFILE config set plugins.entries.hermes-toolset.settings.apply_runtime_defaults false`,
then restore the desired settings, for example
`hermes -p PROFILE config set approvals.mode manual` and
`hermes -p PROFILE config set approvals.destructive_slash_confirm true`.
It runs OMH doctor after setup. Native Hermes installation has no post-install
hook, so the setup command is required after installing this repository.
Use `hermes toolset setup --dry-run` to preview target profiles.

## Hindsight memory per profile

[Hindsight](https://hermes-agent.nousresearch.com/docs/plugins/hindsight) is the
bundle's long-term memory provider. Setup assigns each profile a unique static
bank ID and, in embedded mode, a separate daemon/database profile. Names include
a hash of the profile home so separate Hermes roots cannot accidentally reuse
the same embedded store. CLI, Telegram, and other channels belonging to one
profile share that profile's memory. Profiles do not share banks.

New profiles use automatic recall, automatic retention, and `hybrid` mode
(context injection plus retain/recall/reflect tools). Setup selects Hindsight as
`memory.provider` and disables built-in MEMORY.md/USER.md injection and the
built-in memory tool. Existing files and OMH stores are kept; old memories are
not automatically migrated into Hindsight. The main chat model stays unchanged.

For local embedded memory with Ollama, start from
[plugins/hindsight.example.json](plugins/hindsight.example.json). Install the
chosen Ollama model first; the example uses Hindsight's documented `gemma3:12b`
default. Setup does not download an LLM or choose one silently.

```sh
hermes toolset setup --yes-deps --hindsight-config plugins/hindsight.example.json --dry-run
hermes toolset setup --yes-deps --hindsight-config plugins/hindsight.example.json
```

Other connection-file choices:

- Cloud: `{"mode":"cloud"}`; configure `HINDSIGHT_API_KEY` in each profile's
  `.env` or secret provider.
- Existing server: `{"mode":"local_external","api_url":"http://localhost:8888"}`;
  add profile-specific authentication if that server requires it.
- Embedded with a hosted LLM: set `mode` to `local_embedded`, `llm_provider`
  and `llm_model` to supported values, and optionally `llm_base_url`.
  Configure `HINDSIGHT_LLM_API_KEY` in each profile's `.env` or secret provider.

Connection templates cannot contain credentials. Existing per-profile
connection settings, tuning, and unique bank IDs are preserved on repeat setup.
If no connection is configured, setup reports the missing backend instead of
activating an unconfigured provider. A shared bank, shared embedded daemon,
dynamic bank template, or cross-bank recall setting must be resolved first;
setup refuses to redirect existing memories silently.
Legacy `~/.hindsight/config.json` or environment-based bank routing must first
be localized to explicit per-profile configurations; setup does not silently
shadow those existing stores. Isolation preparation also runs for the bare
installer because native plugin installation can select a memory provider.

To configure only Hindsight after it is installed, use the helper from this
checkout with an explicit list of profiles:

```sh
python3 install-hindsight.py --hermes-home "$HOME/.hermes" \
  --profile default --profile work --config /path/to/connection.json
hermes -p work memory status
```

Repeat setup after creating a profile; `--bundle-only` does not configure external
memory providers. Restart an existing CLI session after changing providers.
Embedded servers start lazily on first use. `memory status` checks provider
availability, not a successful server connection or retain/recall cycle; verify
that cycle with a harmless fact before relying on memory. Banks isolate normal
plugin routing, not access by someone who controls the shared server or PC.

Hermes may flag the bundled workflow scripts during installation. Review its
findings; the plain install command can require an explicit scanner override.
Setup never bypasses scans for imported plugins or skills. Some upstream skills
currently trigger hard blocks that even Hermes's `--force` cannot override.

`--yes-deps` consents to declared plugin dependencies. Security scans remain
enabled; blocked imports make setup fail and need review. Existing installations
are preserved. No gateways are restarted automatically.

## Telegram setup

Setup applies this entry to profiles containing hermes-toolset. For a manual
installation, merge it into the selected profile's `config.yaml`:

```yaml
plugins:
  entries:
    hermes-toolset:
      allow_gateway_injection: true
```

This lets a skill command queue an agent turn in the chat where it was invoked.
The CLI REPL can queue turns without this setting; gateway and TUI injection
require it. Enable the plugin using the command above as well.

Restart the gateway, and reopen any running CLI chat:

```sh
hermes gateway restart
# For a named profile: hermes -p PROFILE gateway restart
```

Requires a current Hermes build with `register_skill`, `register_command`,
and `inject_message(..., origin=...)` support. The manifest declares PyYAML for
Bot Forge, whose upstream manifest currently omits that dependency. Hermes needs its normal model and Telegram
configuration; individual skills may require their own tools.

## OMH runtime troubleshooting

A passing standalone OMH doctor does not prove that the live Hermes plugin can
bind its runtime store. If chat reports `RuntimeBindingError`, ask the agent to
invoke `omh_status` without home overrides to obtain the specific refusal.
For a missing profile binding, point Hermes at the existing OMH store; do not
create a replacement store or overwrite managed skills. With the default setup
layout, use:

```sh
hermes config set plugins.entries.omh.settings.omh_home "$HOME/.hermes/omh"
omh --omh-home "$HOME/.hermes/omh" --hermes-home "$HOME/.hermes" doctor
```

Substitute the actual existing store and profile home if they differ. For a named
profile, also use `hermes -p PROFILE config set` for that profile's setting.
Retry the native `omh_status` tool in chat; successful runtime reads verify the
binding fix. Other binding failures require diagnosis, not this setting change.

## Commands

Use `/toolset` for plugin versions, load status, registered tool/command/skill/hook
counts, and unavailable imports. These are registered capabilities, not a claim
that every tool is enabled in the current chat. Hermes's `/toolsets` lists tool
groups; plugins that provide skills, commands, or hooks need not appear there.
Use `/toolset list` in CLI chat or Telegram for the installed command inventory,
or `/toolset omh` to filter it. `hermes toolset doctor --json` reports plugin load
errors and missing imports. Imported native commands keep their own handlers;
imported plugin skills without commands receive aliases. Telegram's menu has a
capacity limit, so some commands must be typed rather than selected in the menu.

| Hermes CLI chat | Telegram | Purpose |
| --- | --- | --- |
| `/autogoal` | `/autogoal` | Run the autonomous goal workflow |
| `/git-commit-push` | `/git_commit_push` | Commit and push scoped changes |
| `/git-pull-merge` | `/git_pull_merge` | Pull and merge changes |
| `/lgtm` | `/lgtm` | Continue from an approved checkpoint |
| `/repo-docs` | `/repo_docs` | Maintain repository documentation |

For example, type `/repo-docs update the architecture documentation` in Hermes
CLI chat, or `/git_commit_push only src/; no push` in Telegram. Arguments are
passed as text to the skill, never executed as a shell command by the plugin.
These are conversational slash commands, not new `hermes <skill>` shell
subcommands. The agent loads the skill through `skill_view` and performs its
instructions using the current conversation and tools.

Bundled skills also remain available by their qualified names, such as
`hermes-toolset:repo-docs`. Supporting files stay next to their `SKILL.md`. Shared contracts live in
[`skills/shared`](skills/shared/COMMON-CONTRACT.md), alongside the skill folders;
the legacy skill copier preserves that support directory too. Resolve helper
commands from the loaded bundle rather than assuming `~/.hermes/shared-skills`.
Generated autogoal ledger commands use quoted paths to the bundled helper.
An existing built-in or previously registered plugin command wins a name
collision; the skipped alias produces a warning and the qualified skill remains
available. Choose distinctive names to avoid collisions with other plugins,
local skills, and configured quick commands.

Repo-docs and autogoal decide routine engineering choices autonomously within the
accepted scope. They carry decisions into worker contracts and apply relevant
[Addy agent-skills](https://github.com/addyosmani/agent-skills) throughout planning,
implementation and verification, including API, UI, migration, CI and operational
work. Handoffs identify the skill used, the artifact or decision it informed, and
its check result. Missing owner intent or authority remains an explicit question;
loading a skill alone is not proof of applying it.

The [engineering cycle](skills/shared/ENGINEERING-CYCLE.md) connects accepted
specs and existing `goals.json`/`TODO.md` tasks to targeted installed engineering
skills, implementation, checks, native review and owner-ledger reconciliation.
A documentation-only `/repo-docs` request does not launch workers. To continue
through a spec, explicitly ask `/autogoal` to implement that accepted spec within
its stated scope. Default `/autogoal` hands off one slice. Review acceptance and
executed evidence precede canonical closure; no push or deployment is implied.
Skill availability and support files are checked at use time; a missing skill is
reported with its safe fallback, not silently treated as loaded.

## Add or update a skill

```text
skills/
  my-skill/
    SKILL.md
    references/   # optional
    scripts/      # optional
```

Use a folder name of 1–32 lowercase letters, digits, hyphens, or underscores,
starting with a letter or digit. The folder determines the command name; keep
the skill's frontmatter `name` consistent with it. Underscores become hyphens
in CLI commands and Telegram uses underscores: `my_skill` becomes `/my-skill`
in CLI chat and `/my_skill` in Telegram. `my-skill` and `my_skill` cannot coexist.

Every immediate child containing `SKILL.md` is discovered at plugin startup.
Folders without that file are ignored. Invalid names, ambiguous aliases, or
skill paths pointing outside the bundle cause an explicit plugin-load error.

For a GitHub installation, publish your skill changes and run:

```sh
hermes plugins update hermes-toolset
hermes gateway restart
```

Follow any Hermes request to stop a running gateway before updating. For a local
symlink installation, edit this checkout and restart instead. New commands are
discovered on startup, not watched live. Telegram's menu has limited capacity;
Hermes controls which commands appear there.

## Verify

```sh
python scripts/check.py
python scripts/check.py --list
python -m py_compile __init__.py bundle.py install-omh.py install-graphify.py
```

The checker runs top-level and maintained bundled workflow tests in separate
Python processes, with a 180-second timeout per directory. `--list` prints the
inventory without importing tests. Model, installed native backend and optional
integration suites are explicitly excluded with reasons; live opt-in flags are
removed from test subprocesses. Passing this gate does not qualify model/native
execution. Tests use temporary Git fixtures and may write offline scratch receipts.

`tests/integration_plugin.py` additionally checks the actual Hermes manifest
reader, loader, bundled skill reader, Telegram menu, CLI queue, gateway routing,
and unload behavior. Run it using Hermes' Python environment with the Hermes
source root on `PYTHONPATH`. It uses a temporary profile and a capture callback
instead of sending Telegram messages or calling a model.

`tests/integration_bundle.py` checks an existing isolated `HERMES_HOME`: all
loaded skill content, CLI queues and captured gateway routing for every generated
alias, plus the expected-import inventory. Run it with the same Hermes Python
environment and source `PYTHONPATH`. It exits nonzero for missing or blocked
imports. Native command registration is inspected; upstream actions, external
services, and live Telegram delivery are not invoked.

`tests/integration_hindsight.py /path/to/installed/hindsight` uses the same
Hermes interpreter and source path. It creates temporary profiles, loads the
real provider, and captures SDK retain/recall calls to verify bank isolation
and memory-provider diagnostics. It does not start a daemon, contact a server,
or prove extraction quality from a live model.

From this repository's root, use the installed Hermes interpreter and source
checkout (adjust `HERMES_SOURCE` if Hermes is installed elsewhere):

```sh
HERMES_PYTHON="$(hermes --print-runtime-command --module runpy | python -c 'import json, sys; print(json.load(sys.stdin)[0])')"
HERMES_SOURCE="$HOME/.hermes/hermes-agent"
PYTHONPATH="$HERMES_SOURCE" "$HERMES_PYTHON" -c 'import hermes_bootstrap, runpy, sys; runpy.run_path(sys.argv[1], run_name="__main__")' tests/integration_plugin.py
```

For the full bundle check, first provide an existing isolated profile where the
bundle and its declared imports have already been installed. Do not point this
check at your live profile; plugin loading may write runtime records.

```sh
HERMES_HOME="/path/to/isolated-installed-profile" PYTHONPATH="$HERMES_SOURCE" "$HERMES_PYTHON" -c 'import hermes_bootstrap, runpy, sys; runpy.run_path(sys.argv[1], run_name="__main__")' tests/integration_bundle.py
```

The offline suite runs in GitHub Actions. Live Telegram delivery and model
execution require your configured Hermes installation.
