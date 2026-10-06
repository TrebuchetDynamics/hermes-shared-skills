#!/usr/bin/env bash
# One-shot setup of hermes-shared-skills on a new machine (or a fresh ~/.hermes).
#
#   git clone https://github.com/XelHaku/hermes-shared-skills ~/.hermes/shared-skills
#   ~/.hermes/shared-skills/bootstrap.sh [--impeccable] [--no-cleanup-cron] [--dry-run]
#
# 1. Checks that Hermes is installed (prints the official installer otherwise).
# 2. Wires the default profile: skills.external_dirs, monitor + cleanup wrappers, Telegram menu
#    pins (if Telegram is configured), and the SOUL snippets from extras/soul/.
# 3. Schedules the weekly no-agent scratch cleanup in the default profile (idempotent).
# 4. Optionally installs impeccable from upstream with the Hermes overlay.
# Then add project profiles with: extras/new_profile.sh <name> <workspace> [--deliver telegram:<chat>]
set -euo pipefail
repo=$(cd "$(dirname "$0")" && pwd)
impeccable="" cleanup=true dry=""
while [ $# -gt 0 ]; do
  case "$1" in
    --impeccable) impeccable=--impeccable; shift;;
    --no-cleanup-cron) cleanup=false; shift;;
    --dry-run) dry=--dry-run; shift;;
    -h|--help) sed -n '2,13p' "$0"; exit 0;;
    *) echo "unknown option $1" >&2; exit 2;;
  esac
done

if ! command -v hermes >/dev/null; then
  echo "Hermes Agent is not installed. Install it first:" >&2
  echo "  curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash" >&2
  exit 1
fi
hermes_home=${HERMES_HOME:-$HOME/.hermes}
if [ "$repo" != "$hermes_home/shared-skills" ]; then
  echo "note: repo is at $repo; skills and templates assume $hermes_home/shared-skills (symlink it there)." >&2
fi

"$repo/install.sh" --profiles default --telegram-menu --soul $impeccable $dry

if $cleanup && [ -z "$dry" ]; then
  if hermes cron list 2>/dev/null | grep -q 'scratch-cleanup-weekly'; then
    echo "scratch-cleanup-weekly already scheduled"
  else
    hermes cron create "17 4 * * 0" --name scratch-cleanup-weekly --script scratch_cleanup.py --no-agent --deliver local
  fi
fi

cat <<EOF

Next steps:
  - Add a project profile:   $repo/extras/new_profile.sh <name> <workspace> [--deliver telegram:<chat_id>]
  - Optional fleet governor: see extras/cron/README.md (default profile, every 2h).
  - Optional plugin used by this fleet: omh (third-party; install it per its own instructions).
  - Update later with:       git -C $repo pull
EOF
