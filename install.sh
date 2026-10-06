#!/usr/bin/env bash
# Wire hermes-shared-skills into Hermes profiles.
#
#   install.sh --profiles default,myproject [--disable-fleet] [--telegram-menu] [--impeccable] [--dry-run]
#
# Per profile: adds this folder to skills.external_dirs, writes cron monitor wrappers into the
# profile's scripts/ folder, optionally disables the fleet-* skills (project profiles) and pins the
# commands in the Telegram menu. Cron jobs are not created automatically; see extras/cron/README.md.
set -euo pipefail
repo=$(cd "$(dirname "$0")" && pwd)
profiles="" disable_fleet=false telegram_menu=false impeccable=false dry_run=false
while [ $# -gt 0 ]; do
  case "$1" in
    --profiles) profiles=$2; shift 2;;
    --disable-fleet) disable_fleet=true; shift;;
    --telegram-menu) telegram_menu=true; shift;;
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
agent_dir=$(python3 -c 'import json,re,sys; print(re.search(r"sys.path.insert\(0, .([^\x27\x22]+)", json.loads(sys.argv[1])[-1]).group(1))' "$runtime")

export INSTALL_ARGS
INSTALL_ARGS=$(python3 -c 'import json,sys; print(json.dumps({"repo": sys.argv[1], "profiles": sys.argv[2].split(","),
  "disable_fleet": sys.argv[3]=="true", "telegram_menu": sys.argv[4]=="true", "dry_run": sys.argv[5]=="true"}))' \
  "$repo" "$profiles" "$disable_fleet" "$telegram_menu" "$dry_run")
"$py" -I -c "import os, sys, runpy; sys.path.insert(0, '$agent_dir'); os.environ.setdefault('HERMES_HOME', os.path.expanduser('~/.hermes')); import hermes_bootstrap; runpy.run_path('$repo/extras/install_helper.py', run_name='__main__')"

if $impeccable && ! $dry_run; then "$repo/extras/impeccable/sync_impeccable.sh"; fi
echo "Done. Verify with: hermes -p <profile> skills list | grep external"
