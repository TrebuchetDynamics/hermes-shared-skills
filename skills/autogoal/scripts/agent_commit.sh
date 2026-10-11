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
[ $# -ge 5 ] || { echo "usage: agent_commit.sh repo profile card message file..." >&2; exit 2; }
repo=$1 profile=$2 card=$3 msg=$4; shift 4
[ $# -gt 0 ] || { echo "no files given" >&2; exit 2; }
cd "$repo"
repo=$(pwd -P)
branch="agent/$profile/$card"
ref="refs/heads/$branch"
case "$branch" in agent/*/*) ;; *) echo "bad branch $branch" >&2; exit 2;; esac
# Literal files only: a directory or Git pathspec could sweep in foreign work.
python3 - "$repo" "$profile" "$card" "$@" <<'PYVALIDATE'
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
repo, profile, card, *files = sys.argv[1:]
for token in (profile, card):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', token) or '..' in token or token.endswith(('.', '.lock')):
        sys.exit('invalid profile/card ref component')
for name in files:
    path = PurePosixPath(name)
    target = Path(repo) / name
    if (path.is_absolute() or name.startswith(':') or '..' in path.parts or
            '.git' in path.parts or name in ('', '.') or target.is_dir() or
            not target.parent.resolve().is_relative_to(Path(repo))):
        sys.exit('explicit root-relative owned files required: ' + name)
branch = 'refs/heads/agent/' + profile + '/' + card
worktrees = subprocess.check_output(['git', 'worktree', 'list', '--porcelain'], text=True)
if 'branch ' + branch in worktrees.splitlines():
    sys.exit('ref is checked out; refusing to change its HEAD')
PYVALIDATE
export GIT_LITERAL_PATHSPECS=1
old=$(git rev-parse -q --verify "$ref" || true)
parent=${old:-$(git rev-parse HEAD)}
for f in "$@"; do
  if [ ! -e "$f" ] && [ ! -L "$f" ] && ! git cat-file -e "$parent:$f" 2>/dev/null; then
    # A retained owned-file list may include an already committed deletion.
    # Require real provenance in this task's ancestry, never accept a typo.
    history=$(git log -1 --format=%H "$parent" -- "$f")
    if [ -z "$history" ]; then
      echo "owned file does not exist in worktree, parent or task history: $f" >&2
      exit 2
    fi
  fi
done
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
  if [ -e "$f" ] || [ -L "$f" ]; then git add -- "$f"; else git rm -q --cached --ignore-unmatch -- "$f"; fi
done
tree=$(git write-tree)
if [ "$tree" = "$(git rev-parse "$parent^{tree}")" ]; then print_identity "$parent" " (no changes)"; exit 0; fi
commit=$(git commit-tree "$tree" -p "$parent" -m "$msg

Card: $card
Profile: $profile")
git update-ref "$ref" "$commit" "${old:-0000000000000000000000000000000000000000}"
print_identity "$commit"
