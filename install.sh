#!/usr/bin/env bash
# Wire hermes-shared-skills into Hermes profiles.
#
#   install.sh [--profiles default,myproject] [--skip-sync] [--dry-run] [options]
#
# Default: fetch configured upstream, privately back up and discard tracked edits/local
# commits, re-exec the fetched installer, then wire all native live Hermes profiles.
# Untracked/ignored files survive; conflicting paths stop setup. No cron or policy changes
# unless explicitly requested. Run only on a quiescent checkout. See --help and README.
# Optional setup: --replace-root OLD_PATH, --disable-fleet, --telegram-menu, --soul,
# --allow-all, --prune, --impeccable (vendored skills).
set -euo pipefail
repo=$(cd "$(dirname "$0")" && pwd)
original_args=("$@")
profiles="" replace_root="" disable_fleet=false telegram_menu=false soul=false allow_all=false prune=false impeccable=false dry_run=false skip_sync=false
while [ $# -gt 0 ]; do
  case "$1" in
    --profiles|--replace-root)
      [ $# -ge 2 ] && [ -n "$2" ] && [[ "$2" != --* ]] || { printf '%s requires a non-empty value\n' "$1" >&2; exit 2; }
      if [ "$1" = --profiles ]; then profiles=$2; else replace_root=$2; fi
      shift 2;;
    --disable-fleet) disable_fleet=true; shift;;
    --telegram-menu) telegram_menu=true; shift;;
    --soul) soul=true; shift;;
    --allow-all) allow_all=true; shift;;
    --prune) prune=true; shift;;
    --impeccable) impeccable=true; shift;;
    --skip-sync|--keep-local) skip_sync=true; shift;;
    --dry-run) dry_run=true; shift;;
    -h|--help)
      printf '%s\n' \
        'Usage: install.sh [--profiles a,b] [--skip-sync|--keep-local] [--dry-run] [options]' \
        'Default: fetch configured upstream; back up and discard tracked/index edits and local-only commits;' \
        'then set up all native live Hermes profiles, including default. Run without concurrent writers.' \
        'Untracked/ignored files survive; path collisions fail closed. No git clean or recursive submodule reset.' \
        'Backups: ~/.hermes/private-records/shared-skills/install-backups/; old HEAD: refs/install-backups/.' \
        '--profiles narrows setup only. --skip-sync keeps local work. --dry-run makes no Git/profile writes.' \
        'Optional: --replace-root OLD_PATH --disable-fleet --telegram-menu --soul --allow-all --prune --impeccable' \
        'No cron jobs or approval/SOUL/pruning changes by default. See README for recovery.'
      exit 0;;
    *) echo "unknown option $1" >&2; exit 2;;
  esac
done
command -v hermes >/dev/null || { echo "hermes CLI not found on PATH" >&2; exit 1; }

# Parse this entire block before a reset replaces the running script. Re-exec
# the fetched installer so its option handling and helper always match.
if ! $skip_sync; then
  if $dry_run; then
    python3 "$repo/extras/install/sync_repo.py" "$repo" --dry-run
  else
    python3 "$repo/extras/install/sync_repo.py" "$repo"
    exec bash "$repo/install.sh" "${original_args[@]}" --skip-sync
  fi
fi

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
INSTALL_ARGS=$(python3 -c 'import json,sys; print(json.dumps({"repo": sys.argv[1], "profiles": sys.argv[2].split(",") if sys.argv[2] else None, "native_profiles": True,
  "disable_fleet": sys.argv[3]=="true", "telegram_menu": sys.argv[4]=="true", "dry_run": sys.argv[5]=="true",
  "soul": sys.argv[6]=="true", "allow_all": sys.argv[7]=="true", "prune": sys.argv[8]=="true", "replace_root": sys.argv[9]}))' "$repo" "$profiles" "$disable_fleet" "$telegram_menu" "$dry_run" "$soul" "$allow_all" "$prune" "$replace_root")
"$py" -I -c 'import sys, runpy; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from pm.environments import activate_dependencies; activate_dependencies(Path(sys.argv[1])); runpy.run_path(sys.argv[2], run_name="__main__")' "$agent_dir" "$repo/extras/install/install_helper.py"

if $impeccable && ! $dry_run; then python3 "$repo/extras/vendor/sync_vendor.py"; fi   # --impeccable kept as the "install vendored skills" switch
echo "Done. Verify with: hermes -p <profile> skills list | grep external"
