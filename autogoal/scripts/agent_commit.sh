#!/usr/bin/env bash
# Commit a card's files to a local agent branch WITHOUT touching the shared checkout.
#
#   agent_commit.sh <repo> <profile> <card-id> "<message>" <file>...
#
# Branch: agent/<profile>/<card-id>, parented on its existing tip, else on HEAD.
# Uses a temporary index, so HEAD, the real index, the working tree and other
# agents' dirty work are untouched. Never pushes, never touches main/master.
# Prints the branch and new commit sha.
set -euo pipefail
repo=$1 profile=$2 card=$3 msg=$4; shift 4
[ $# -gt 0 ] || { echo "no files given" >&2; exit 2; }
cd "$repo"
branch="agent/$profile/$card"
ref="refs/heads/$branch"
case "$branch" in agent/*/*) ;; *) echo "bad branch $branch" >&2; exit 2;; esac
parent=$(git rev-parse -q --verify "$ref" || git rev-parse HEAD)
tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
export GIT_INDEX_FILE=$tmp
git read-tree "$parent"
for f in "$@"; do
  if [ -e "$f" ]; then git add -- "$f"; else git rm -q --cached --ignore-unmatch -- "$f"; fi
done
tree=$(git write-tree)
if [ "$tree" = "$(git rev-parse "$parent^{tree}")" ]; then echo "$branch $parent (no changes)"; exit 0; fi
commit=$(git commit-tree "$tree" -p "$parent" -m "$msg

Card: $card
Profile: $profile")
git update-ref "$ref" "$commit" "$(git rev-parse -q --verify "$ref" || echo 0000000000000000000000000000000000000000)"
echo "$branch $commit"
