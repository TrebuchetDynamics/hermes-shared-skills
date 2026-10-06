#!/usr/bin/env bash
# Sync shared-skills/impeccable from upstream pbakaus/impeccable (.hermes build), then
# re-append the Hermes fleet overlay. Usage: sync_impeccable.sh [git-ref]   (default: main)
set -euo pipefail
ref=${1:-main}
here=$(cd "$(dirname "$0")" && pwd)
hermes_home=${HERMES_HOME:-$HOME/.hermes}
dest=$(cd "$here/../.." && pwd)/impeccable
overlay=$here/overlay.md
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

git clone -q --depth 1 --branch "$ref" --filter=blob:none --sparse https://github.com/pbakaus/impeccable "$tmp/imp"
git -C "$tmp/imp" sparse-checkout set .hermes
rev=$(git -C "$tmp/imp" rev-parse HEAD)
src="$tmp/imp/.hermes/skills/impeccable"
mkdir -p "$dest"; [ -f "$src/SKILL.md" ] || { echo "upstream .hermes build missing" >&2; exit 1; }

backup=$hermes_home/backups/impeccable-$(date +%Y%m%d-%H%M%S)
mkdir -p "$backup" && cp -a "$dest" "$backup/"
rsync -a --delete --exclude '.upstream' "$src/" "$dest/"
cat "$overlay" >> "$dest/SKILL.md"
printf 'source: https://github.com/pbakaus/impeccable/tree/%s/.hermes/skills/impeccable\nsynced: %s\noverlay: %s (appended to SKILL.md)\nupdate: %s\n' \
  "$rev" "$(date -u +%Y-%m-%dT%H:%MZ)" "$overlay" "$0" > "$dest/.upstream"
echo "synced $rev (backup $backup)"
