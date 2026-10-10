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
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$1 profile=$2 card=$3 msg=$4; shift 4
[ $# -gt 0 ] || { echo "no files given" >&2; exit 2; }
cd "$repo"
repo=$(pwd -P)
branch="agent/$profile/$card"
ref="refs/heads/$branch"
case "$branch" in agent/*/*) ;; *) echo "bad branch $branch" >&2; exit 2;; esac
old=$(git rev-parse -q --verify "$ref" || true)
parent=${old:-$(git rev-parse HEAD)}
print_identity() {
  if [ "${AGENT_COMMIT_JSON:-0}" = 1 ]; then
    identity_ref=$(git rev-parse -q --verify "$ref" >/dev/null && printf '%s' "$ref" || printf '%s' "$parent")
    python3 -c 'import json,sys; sys.path.insert(0,sys.argv[1]); import candidate_identity; print(json.dumps(candidate_identity.capture(sys.argv[2],sys.argv[3],sys.argv[4])))' "$script_dir" "$repo" "$parent" "$identity_ref"
  else
    echo "$branch $1${2:-}"
  fi
}
tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
export GIT_INDEX_FILE=$tmp
git read-tree "$parent"
for f in "$@"; do
  if [ -e "$f" ]; then git add -- "$f"; else git rm -q --cached --ignore-unmatch -- "$f"; fi
done
tree=$(git write-tree)
if [ "$tree" = "$(git rev-parse "$parent^{tree}")" ]; then print_identity "$parent" " (no changes)"; exit 0; fi
commit=$(git commit-tree "$tree" -p "$parent" -m "$msg

Card: $card
Profile: $profile")
git update-ref "$ref" "$commit" "${old:-0000000000000000000000000000000000000000}"
print_identity "$commit"
