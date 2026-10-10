#!/usr/bin/env bash
# Behind-only realignment of a shared, multi-writer checkout: move the pointer to the source
# commit WITHOUT writing any worktree byte that was not verified clean. See the skill's
# "Behind-only realignment is the bounded exception" bullet for when this is legitimate.
#
#   usage: behind-only-realign.sh [<source-ref>]        # default: @{u}
#   env:   REALIGN_SAFETY_REF     safety branch name (default safety/pre-pull-<date>)
#          REALIGN_EXCLUDE_RE     ERE of paths excluded from the STRICT PROOF only — live
#                                 runtime data that changes by design, e.g. '^rig-vigia/(data|logs)/'
#
# Aborts unless: HEAD is an ancestor of the source, nothing is staged, no index.lock.
# Nothing is ever discarded, stashed, rebased or reset --hard.
set -euo pipefail
REPO_ROOT=$(git rev-parse --show-toplevel); cd "$REPO_ROOT"
SRC=${1:-@{u}}
NEW=$(git rev-parse "$SRC"); OLD=$(git rev-parse HEAD)
SAFETY_REF=${REALIGN_SAFETY_REF:-safety/pre-pull-$(date +%Y%m%d)}

# --- preconditions the exception requires -----------------------------------
git merge-base --is-ancestor HEAD "$SRC" || { echo "ABORT: local-only commits exist (not behind-only)"; exit 1; }
[ "$(git diff --cached --name-only | wc -l)" -eq 0 ] || { echo "ABORT: index not pristine (a writer is staged)"; exit 1; }
[ -e "$(git rev-parse --git-dir)/index.lock" ] && { echo "ABORT: index.lock present"; exit 1; } || true

W=$(mktemp -d)
git diff --name-only > "$W/modified"                        # tracked: modified or deleted
LS_FILES=$(git ls-files --others --exclude-standard)
printf '%s\n' "$LS_FILES" > "$W/untracked"                 # untracked files
# Never write any path in here: untracked counts as dirty (that is the whole trap).
LC_ALL=C sort -u "$W/modified" "$W/untracked" > "$W/local"
grep -vE "${REALIGN_EXCLUDE_RE:-^\$}" "$W/local" > "$W/assert" || true

snap() { while IFS= read -r p; do
    [ -z "$p" ] && continue
    if [ -e "$p" ]; then printf '%s %s\n' "$p" "$(git hash-object -- "$p")"
    else printf '%s ABSENT\n' "$p"; fi
  done < "$1" | LC_ALL=C sort; }
snap "$W/assert" > "$W/before"

git branch --no-track "$SAFETY_REF" "$OLD" 2>/dev/null || echo "  (safety ref $SAFETY_REF already existed)"
git reset --mixed "$NEW" >/dev/null                        # moves the ref + index; writes no file

git diff --name-only "$OLD" "$NEW" | LC_ALL=C sort -u > "$W/incoming"
LC_ALL=C comm -23 "$W/incoming" "$W/local" > "$W/cand"      # clean by BOTH definitions
while IFS= read -r p; do [ -n "$p" ] && [ -e "$p" ] && printf '%s\n' "$p"; done \
  < "$W/cand" > "$W/refresh"
[ -s "$W/refresh" ] && xargs -d '\n' git checkout "$NEW" -- < "$W/refresh"

snap "$W/assert" > "$W/after"
CHANGED=$(LC_ALL=C diff "$W/before" "$W/after" | grep -c '^[<>]' || true)
echo "OLD=$OLD"; echo "NEW=$NEW"
echo "ADVANCED_CLEAN_PATHS=$(wc -l < "$W/refresh")  PRESERVED_ASSERTED=$(wc -l < "$W/assert")"
echo "HEAD_NOW=$(git rev-parse --short HEAD)  UPSTREAM_NOW=$(git rev-parse --short "$SRC")  SAFETY_REF=$SAFETY_REF"
# Report tail must never abort the script: diff exits 1 when it finds differences (by design).
if [ "$CHANGED" -eq 0 ]; then echo "PROOF=ZERO_CHANGED (every asserted writer file byte-identical)"
else echo "PROOF=CHANGED ($CHANGED lines) — attribute each one before reporting:"; LC_ALL=C diff "$W/before" "$W/after" | head -20 || true; fi
echo "WORK=$W"
