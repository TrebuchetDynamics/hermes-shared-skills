#!/usr/bin/env bash
# Wire hermes-shared-skills into Hermes profiles.
#
#   install.sh --profiles default,myproject [--disable-fleet] [--telegram-menu] [--soul] [--allow-all] [--prune] [--impeccable] [--dry-run]
#
# Per profile: adds this folder to skills.external_dirs, writes cron monitor wrappers into the
# profile's scripts/ folder, optionally disables the fleet-* skills (project profiles) and pins the
# commands in the Telegram menu, and appends the extras/soul/ snippets to SOUL.md (--soul), and turns off every approval
# prompt including the protected AGENTS.md/SOUL.md write gate (--allow-all), and disables the audited unused skills in extras/install/disabled-skills.txt (--prune). Cron jobs are not created automatically; see extras/cron/README.md.
set -euo pipefail
repo=$(cd "$(dirname "$0")" && pwd)
profiles="" disable_fleet=false telegram_menu=false soul=false allow_all=false prune=false impeccable=false dry_run=false
while [ $# -gt 0 ]; do
  case "$1" in
    --profiles) profiles=$2; shift 2;;
    --disable-fleet) disable_fleet=true; shift;;
    --telegram-menu) telegram_menu=true; shift;;
    --soul) soul=true; shift;;
    --allow-all) allow_all=true; shift;;
    --prune) prune=true; shift;;
    --impeccable) impeccable=true; shift;;
    --dry-run) dry_run=true; shift;;
    -h|--help) sed -n '2,9p' "$0"; exit 0;;
    *) echo "unknown option $1" >&2; exit 2;;
  esac
done
[ -n "$profiles" ] || { echo "--profiles is required (e.g. --profiles default,myproject)" >&2; exit 2; }
command -v hermes >/dev/null || { echo "hermes CLI not found on PATH" >&2; exit 1; }

# Borrow Hermes' runtime Python (it has ruamel.yaml) via its own launcher description.
runtime=$(hermes --print-runtime-command)
py=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])[0])' "$runtime")
agent_dir=$(python3 -c 'import ast,json,sys
code = ast.parse(json.loads(sys.argv[1])[-1])
for node in ast.walk(code):
    if isinstance(node, ast.Call) and ast.unparse(node.func) == "sys.path.insert" and len(node.args) == 2 and ast.literal_eval(node.args[0]) == 0:
        path = ast.literal_eval(node.args[1])
        if isinstance(path, str):
            print(path)
            break
else:
    raise SystemExit("Hermes runtime command has no source-root sys.path.insert")' "$runtime")

export INSTALL_ARGS
INSTALL_ARGS=$(python3 -c 'import json,sys; print(json.dumps({"repo": sys.argv[1], "profiles": sys.argv[2].split(","),
  "disable_fleet": sys.argv[3]=="true", "telegram_menu": sys.argv[4]=="true", "dry_run": sys.argv[5]=="true",
  "soul": sys.argv[6]=="true", "allow_all": sys.argv[7]=="true", "prune": sys.argv[8]=="true"}))' "$repo" "$profiles" "$disable_fleet" "$telegram_menu" "$dry_run" "$soul" "$allow_all" "$prune")
"$py" -I -c 'import os, sys, runpy; sys.path.insert(0, sys.argv[1]); os.environ.setdefault("HERMES_HOME", os.path.expanduser("~/.hermes")); import hermes_bootstrap; runpy.run_path(sys.argv[2], run_name="__main__")' "$agent_dir" "$repo/extras/install/install_helper.py"

if $impeccable && ! $dry_run; then python3 "$repo/extras/vendor/sync_vendor.py"; fi   # --impeccable kept as the "install vendored skills" switch
echo "Done. Verify with: hermes -p <profile> skills list | grep external"
