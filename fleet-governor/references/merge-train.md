# Merge train (daily)

Fleet workers commit only to `agent/<profile>/<card>` branches, and many project repos only accept
pull requests on `main`. Verified work therefore piles up uncommitted in each repo's shared
worktree unless something lands it. The merge train does that once a day, deterministically
(no model):

- Cron: `merge-train-daily` in the default profile, `30 3 * * *`, no-agent. The wrapper
  `merge_train_daily.py` starts `fleet-governor/scripts/merge_train.py launch` detached (gates can
  outlive the cron script limit) and prints nothing.
- Output: `~/.hermes/fleet-governor/merge-train/<date>.md` (one line per repo) plus `<date>.log`
  (gate output) and `<date>.stdout`.

## Per repo

0. **Agent branches first.** Workers in isolated worktrees (polymarket's `.worktrees/`, for example)
   deliver only on `agent/<profile>/<card>` branches, which nothing else merges. The train merges each
   branch whose kanban card is `done`, oldest first, with real merge commits (card history kept).
   - **Skipped and counted:** already on `main`; card not done; older than 14 days; touches a file
     that is uncommitted in the shared worktree (the worktree phase owns those).
   - **Gate:** the merged tree, the same way as below. A new failure splits the batch in half until
     the failing branches are isolated; the rest land. Conflicting or failing branches are listed.
   - **Sync:** landed files are checked out into the shared worktree so it doesn't show them reverted.
   - Branches are never deleted, rebased or rewritten. Opt out with `{"branches": false}`.
1. **Plan:** dirty, non-ignored paths, minus files modified in the last 30 min (live work),
   nested repos, files over 5 MB and secret-looking paths. A diff with secret-looking content aborts.
2. **Gate:** in an isolated worktree on exactly the candidate tree, with `flutter pub get`, plus
   `npm ci` when node_modules can't be reused.
   - **Where the gate comes from:** `<repo>/.hermes/merge-train.json`, then a `Complete gate:`
     block in AGENTS.md or CLAUDE.md, then component detection (Flutter/Dart, Go, Rust, Node `test`
     script, pytest). Docs-only candidates get `git diff --check`.
   - **No gate for some changed code:** the repo is not landed.
   - **A failure that also happens on `main`** is pre-existing and doesn't block.
   - **Failing Flutter test files that are new or modified** are held back once, then re-gated,
     and become `MT-*` tasks under an `INTEGRATION` goal in goals.json.
   - **A failure in unchanged tests that pass on `main`** is a regression: that repo is not landed.
3. **Land:** one `chore(merge-train)` commit on top of `main`.
   - **Direct push when allowed.** If the branch requires a PR, push `merge-train/<date>-<sha>`,
     open a PR, wait up to 90 min for CI, and merge only when every failing check also fails on `main`.
   - **Never** force-push, rebase, or land when `origin/main` has commits that local `main` lacks.

## Governor duties

- In the sweep after 03:30, read today's report and include it in the cycle report: what landed,
  PRs left open and why, repos not landed and why.
- **Repo not landed for lack of a gate:** route a card to that profile to add a `Complete gate:`
  block to its AGENTS.md (an implementation slice, not an owner question).
- **PR left open on a new failing check:** route a fix card to that profile.
- Opt a repo out with `<repo>/.hermes/merge-train.json`: `{"enabled": false}`.
- **Branches listed as conflicting or failing the gate:** route a card to that profile to merge the
  branch by hand with `git-pull-merge` (or close the card's work as superseded).
- Manual run: `python3 ~/.hermes/shared-skills/fleet-governor/scripts/merge_train.py run [--profiles x]
  [--plan-only | --dry-run]`.
