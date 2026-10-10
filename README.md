# hermes-toolset

A Hermes plugin that turns the skills in this repository into commands in
Hermes CLI chat and Telegram. Add a `skills/<name>/SKILL.md`, update the installed
plugin, and restart Hermes; there is no command list to maintain.

## Install

Once these changes are published to GitHub:

```sh
hermes plugins install TrebuchetDynamics/hermes-toolset
hermes plugins enable hermes-toolset
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
The existing [plugin installer](plugins/README.md) manages other plugins and is
separate from installing this repository itself.

## Telegram setup

Merge this entry into the selected profile's `config.yaml`, preserving existing
plugin configuration:

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
and `inject_message(..., origin=...)` support. No additional Python packages or
API keys are needed by the plugin. Hermes needs its normal model and Telegram
configuration; individual skills may require their own tools.

## Commands

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
`hermes-toolset:repo-docs`. Supporting files stay next to their `SKILL.md`.
An existing built-in or previously registered plugin command wins a name
collision; the skipped alias produces a warning and the qualified skill remains
available. Choose distinctive names to avoid collisions with other plugins,
local skills, and configured quick commands.

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
the skill's frontmatter `name` consistent with it. `my-skill` and `my_skill`
cannot coexist because they map to the same Telegram command.

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
python -m unittest discover -s tests -p 'test_*.py'
python -m py_compile __init__.py
```

`tests/integration_plugin.py` additionally checks the actual Hermes manifest
reader, loader, bundled skill reader, Telegram menu, CLI queue, gateway routing,
and unload behavior. Run it using Hermes' Python environment with the Hermes
source root on `PYTHONPATH`. It uses a temporary profile and a capture callback
instead of sending Telegram messages or calling a model.

The offline suite runs in GitHub Actions. Live Telegram delivery and model
execution require your configured Hermes installation.
