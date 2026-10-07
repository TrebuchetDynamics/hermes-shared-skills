#!/usr/bin/env bash
# Create (or adopt) a project profile wired to hermes-shared-skills, with its cron jobs.
#
#   new_profile.sh <name> <workspace> [--deliver telegram:<chat_id>|local] [--autogoal hourly|15m]
#                  [--description TEXT] [--no-cron] [--dry-run]
#
# Steps: hermes profile create (skipped if it exists) -> terminal.cwd = workspace -> install.sh
# (external_dirs, fleet skills disabled, Telegram menu, SOUL snippets) -> cron jobs from
# extras/cron/: repo-docs-on-change (monitor-gated, every 10 min) and autogoal (with continuity).
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
[ $# -ge 2 ] || { sed -n '2,9p' "$0"; exit 2; }
name=$1 workspace=$(realpath "$2"); shift 2
deliver=local cadence=hourly description="" cron=true dry=false
while [ $# -gt 0 ]; do
  case "$1" in
    --deliver) deliver=$2; shift 2;;
    --autogoal) cadence=$2; shift 2;;
    --description) description=$2; shift 2;;
    --no-cron) cron=false; shift;;
    --dry-run) dry=true; shift;;
    *) echo "unknown option $1" >&2; exit 2;;
  esac
done
[ -d "$workspace" ] || { echo "workspace $workspace does not exist" >&2; exit 1; }
run() { if $dry; then echo "[dry-run] $(printf '%q ' "$@")"; else "$@"; fi; }

if hermes profile list 2>/dev/null | grep -qw -- "$name"; then
  echo "profile $name exists; adopting it"
else
  run hermes profile create "$name" ${description:+--description "$description"}
fi
run hermes -p "$name" config set terminal.cwd "$workspace"
if $dry; then "$repo/install.sh" --profiles "$name" --disable-fleet --telegram-menu --soul --allow-all --prune --dry-run
else "$repo/install.sh" --profiles "$name" --disable-fleet --telegram-menu --soul --allow-all --prune; fi

$cron || exit 0
# Stagger minutes per profile name so profiles do not all fire at once.
m=$(( $(printf '%s' "$name" | cksum | cut -d' ' -f1) % 10 ))
if hermes -p "$name" cron list 2>/dev/null | grep -q 'repo-docs-on-change'; then
  echo "repo-docs-on-change already exists"
else
  run hermes -p "$name" cron create "$m-59/10 * * * *" "$(cat "$repo/extras/cron/repo-docs.prompt.md")" \
    --name repo-docs-on-change --skill repo-docs --workdir "$workspace" --deliver "$deliver" \
    --monitor-script repo_docs_monitor.py
fi
rd_id=$(hermes -p "$name" cron list 2>/dev/null | awk '/repo-docs-on-change/{print prev} {prev=$1}' | grep -oE '[0-9a-f]{12}' | head -1 || true)
case "$cadence" in 15m) sched="$(( (m+3) % 15 ))-59/15 * * * *"; jobname=autogoal-every-15m;; *) sched="$(( (m*6+3) % 60 )) * * * *"; jobname=autogoal-hourly;; esac
if hermes -p "$name" cron list 2>/dev/null | grep -q "$jobname"; then
  echo "$jobname already exists"
else
  prompt=$(sed -e "s|{profile}|$name|g" -e "s|{workspace}|$workspace|g" -e "s|{repo_docs_job_id}|${rd_id:-repo-docs-on-change}|g" "$repo/extras/cron/autogoal.prompt.md")
  run hermes -p "$name" cron create "$sched" "$prompt" --name "$jobname" --skill autogoal \
    --workdir "$workspace" --deliver "$deliver" --continuity
fi
echo "Profile $name ready. Check: hermes -p $name cron list"
