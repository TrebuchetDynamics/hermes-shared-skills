# Plugin installation

From the repository root:

```sh
./install-plugins.sh --dry-run
./install-plugins.sh
```

The script reads `plugins/PLUGINS.md` relative to its own location, so it
also works when called from another directory. Add one catalog URL and scope
per line; blank lines and lines beginning with `#` are ignored:

```text
https://hermes-agent.nousresearch.com/docs/plugins/omh all profiles
https://hermes-agent.nousresearch.com/docs/plugins/bot-forge default profile only
https://github.com/dietrichgebert/ponytail all profiles
skills https://github.com/addyosmani/agent-skills all profiles
```

`all profiles` includes `default` and existing named profiles. Deleted profiles
and directories without Hermes identity markers are excluded. Rerun after
creating a profile to install its plugins. The selected active profile does
not change these rules.

The installer uses `HERMES_HOME`, or `~/.hermes` when unset. A named-profile
home resolves to its containing root. Use `--hermes-home /path/to/hermes-root`
to explicitly select a different installation.

GitHub URLs install native Hermes plugins directly. Prefix a GitHub URL with
`skills` for a skill repository instead: the installer uses Git to clone a
temporary discovery checkout, then calls `hermes skills install` for every
immediate `skills/*/SKILL.md` in each selected profile. Hermes handles existing
skills, scanning, and confirmation; no force-overwrite flag is passed. The
checkout is removed afterwards. These entries require Git. Discovery and
native installs use the default branch; updates during a run can change it.
Dry runs show the repository/profile plan without cloning or fetching skills.

The listed Graphify repository currently ships a Python CLI rather than a
Hermes plugin or standard skill bundle. The installer reports it as unsupported
and exits nonzero after processing the other entries, including in dry-run mode.
It needs a separate integration; it is not silently treated as installed.

Requires Bash, Python 3.9+, and `hermes` on `PATH`. GitHub plugin skips use
Hermes' recorded source metadata so differing repository and plugin names work.
Untracked manual installs are left for Hermes to handle without force-overwrite.
Installation uses the native catalog
command, preserving Hermes' dependency, security, and activation prompts;
run interactively to answer them. The script does not automatically enable
plugins, update existing installs, change memory providers, or restart gateways.
Existing plugin directories are reported as skipped, not verified as enabled.
An install failure is reported, other targets are attempted, and the script
exits nonzero if any target failed. `--dry-run` never invokes Hermes.

Run the isolated installer tests with:

```sh
python -m unittest discover -s tests -p 'test_install_plugins.py'
```

Native command reference: [Hermes plugins](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins).
