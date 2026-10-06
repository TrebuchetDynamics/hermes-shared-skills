# hermes-shared-skills

Shared skills, and therefore slash commands, for a fleet of [Hermes Agent](https://github.com/NousResearch/hermes-agent)
profiles. In Hermes every skill is a command: `/autogoal`, `/repo-docs` (Telegram: `/repo_docs`), and so on.
Profiles, sessions and credentials are not part of this repo.

## Skills / commands

Fleet workflow:

| Command | What it does |
|---|---|
| `/autogoal` | Picks the next goal-linked task (`goals.py next`) and hands it to a native 50-turn goal worker. The picker never implements. |
| `/repo-docs` | Builds or maintains the core docs, keeps `goals.json`, and turns every unmet goal into a TODO.md task. |
| `/git-commit-push` | Ships local changes safely in shared worktrees: stage → gate → push, verify the remote. |
| `/lgtm` | Resolves a short approval against the latest checkpoint without widening scope. |
| `/grill-me` | Stress-tests a plan; also the questionnaire format agents use whenever they need the user. |
| `/hard-blockers` | BLOCKERS.md as the owner's open-questions ledger (defaults applied, work continues). |
| `/fleet-governor`, `/fleet-blockers`, `/fleet-status` | Default-profile fleet coordination (disabled in project profiles). |
| `/impeccable` | Frontend design skill, installed from upstream with a Hermes overlay (see NOTICE). |

Engineering practice, written by the fleet's agents from real incidents:

| Command | Use when |
|---|---|
| `/shared-worktree-commit-safety` | committing a dirty tree other agents may be writing |
| `/codebase-audit-verification`, `/repo-issue-audit` | auditing a repo before reporting issues (read-only) |
| `/docker-build-context-verification` | changing Docker build contexts or `.dockerignore` |
| `/parallel-mechanical-edits`, `/consolidating-shared-constants` | fanning a mechanical change out; deduplicating repeated literals |
| `/local-visual-verification`, `/operator-console-design` | verifying a UI change before claiming done; operator console UIs |
| `/reference-product-port`, `/upstream-reference-verification` | porting a reference product; checking upstream clones and freshness |
| `/repository-knowledge-engineering`, `/repository-maintenance` | building durable repo expertise; syncing repos and submodules |
| `/mobile-release` | releasing mobile apps (version and gate checks) |
| `/recurring-job-management` | tuning a Hermes cron job's schedule or cadence |
| `/understand-anything-hermes` | installing and running Understand-Anything in a profile |
| `/audio-generation` | creating spoken audio |

Project-specific skills (codebase maps, domain triage) stay in their own profiles.

Key design rules shared by these skills:
- **Ask, don't block.** Needing the user means sending a questionnaire and applying reversible defaults, never pausing a goal.
- **The met rule.** A goal in `goals.json` is `met` only with an executed, passing check (`repo-docs/scripts/goals.py`).
- **The review handoff is a goal's last step.** Approval comes afterwards (see `extras/soul/review-handoff.md`).

## Install (new machine or fresh ~/.hermes)

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash        # Hermes itself, if missing
git clone https://github.com/XelHaku/hermes-shared-skills ~/.hermes/shared-skills
~/.hermes/shared-skills/bootstrap.sh                        # default profile + weekly cleanup
~/.hermes/shared-skills/extras/new_profile.sh myproject ~/git/myproject --deliver telegram:<chat_id>
```

- `bootstrap.sh` wires the default profile: `skills.external_dirs`, monitor and cleanup wrappers,
  Telegram menu pins, and the SOUL snippets. It also schedules `scratch-cleanup-weekly`.
- `new_profile.sh` creates or adopts a project profile, sets `terminal.cwd`, wires it (with the fleet
  skills disabled) and creates its `repo-docs-on-change` and `autogoal` cron jobs from `extras/cron/`.
  Use `--autogoal 15m` for busy profiles and `--no-cron` to skip the jobs.
- `install.sh --profiles a,b [--disable-fleet] [--telegram-menu] [--soul] [--dry-run]` re-wires existing
  profiles. It is idempotent.
- Updates: `git -C ~/.hermes/shared-skills pull`. Every profile reads the folder live.

## Vendored third-party skills

`extras/vendor/manifest.json` pins curated skills from other repositories. `extras/vendor/sync_vendor.py`
installs them into `vendor/<source>/<skill>/` (gitignored, so their licenses stay with them).
Each one gets a short Hermes note that maps other harnesses' tool names to Hermes tools and
states that fleet rules win. `bootstrap.sh` runs it; re-run it any time, or with `--pin` to bump
to upstream HEAD. The sync refuses names that collide with first-party or Hermes-bundled skills.

| Source (license) | Commands |
|---|---|
| pbakaus/impeccable (Apache-2.0) | `/impeccable` (+ fleet overlay) |
| DietrichGebert/ponytail (MIT) | `/ponytail`, `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt` |
| mattpocock/skills (MIT) | `/grill-with-docs`, `/session-handoff`, `/prototype`, `/improve-codebase-architecture`, `/domain-modeling`, `/writing-for-agents` |
| ayghri/i-have-adhd (MIT) | `/i-have-adhd` |
| cloudflare/security-audit-skill (MIT) | `/security-audit` |
| obra/superpowers (MIT) | `/verification-before-completion`, `/receiving-code-review`, `/writing-skills` |
| cathrynlavery/diagram-design (MIT) | `/diagram-design` |
| addyosmani/agent-skills (MIT) | `/code-simplification`, `/api-and-interface-design`, `/observability-and-instrumentation`, `/performance-optimization`, `/security-and-hardening`, `/deprecation-and-migration`, `/context-engineering`, `/browser-testing-with-devtools`, `/ci-cd-and-automation` |

Deliberately not vendored: duplicates of bundled or first-party skills (humanizer, TDD,
systematic debugging, code review, grill-me), skills that overlap autogoal, repo-docs or
git-commit-push, skills that force approval gates (superpowers' using-superpowers and
brainstorming), and graphify (a CLI, not a skill; understand-anything-hermes covers it).

## Layout

```
<skill>/SKILL.md (+ references/, scripts/)   one folder per skill = one command
shared/COMMON-CONTRACT.md                     contract several skills follow
extras/monitors/      cron monitor scripts (skip the model when nothing changed)
extras/cron/          cron prompt templates
extras/soul/          SOUL.md snippets every worker must see
extras/impeccable/    upstream sync script + Hermes overlay
extras/maintenance/   scratch_cleanup.py (weekly, no-agent cron; deletes worker scratch older than 7 days)
extras/new_profile.sh create + wire a project profile with its cron jobs
bootstrap.sh          one-shot setup for a new machine
install.sh            per-profile wiring
```

## Tests

```bash
python3 repo-docs/scripts/test_goals.py
for t in autogoal/scripts/test_*.py; do python3 "$t"; done
python3 fleet-blockers/scripts/test_collect.py
```

`repo-docs/scripts/test_goal_gap_regression.py` and `hard-blockers/scripts/test_repo_docs.py` are
behavioral regressions that call a real model through `hermes chat`. Run them manually after policy changes.
