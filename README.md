# hermes-shared-skills

Shared skills, and therefore slash commands, for a fleet of [Hermes Agent](https://github.com/NousResearch/hermes-agent)
profiles. In Hermes every skill is a command: `/autogoal`, `/repo-docs` (Telegram: `/repo_docs`), and so on.
Profiles, sessions and credentials are not part of this repo.

## Skills / commands

| Command | What it does |
|---|---|
| `/autogoal` | Picks the next goal-linked task (`goals.py next`) and hands it to a native 50-turn goal worker. The picker never implements. |
| `/repo-docs` | Builds or maintains the core docs (README, PRD, ADRs, spec, OpenAPI, test plan, runbook, CHANGELOG), keeps `goals.json` and turns every unmet goal into a TODO.md task. |
| `/git-commit-push` | Ships local changes safely in shared worktrees: isolate your own work, stage → gate → push, verify the remote. |
| `/lgtm` | Resolves a short approval against the latest checkpoint without widening scope. |
| `/grill-me` | Stress-tests a plan; also the **questionnaire format** agents use whenever they need the user (ask, don't block). |
| `/hard-blockers` | BLOCKERS.md as the owner's open-questions ledger (defaults applied, work continues). |
| `/fleet-governor`, `/fleet-blockers`, `/fleet-status` | Default-profile fleet coordination. Disable them in project profiles (`skills.disabled`). |
| `/impeccable` | Frontend design skill, installed from upstream with a Hermes overlay (see NOTICE). |

Key design rules shared by these skills:
- **Ask, don't block.** Needing the user means sending a questionnaire and applying reversible defaults, never pausing a goal.
- **The met rule.** A goal in `goals.json` is `met` only with an executed, passing check (`repo-docs/scripts/goals.py`).
- **The review handoff is a goal's last step.** Approval comes afterwards (see `extras/soul/review-handoff.md`).

## Install

The default location is `~/.hermes/shared-skills`. Several skills and templates reference it.

```bash
git clone git@github.com:<you>/hermes-shared-skills.git ~/.hermes/shared-skills
~/.hermes/shared-skills/install.sh --profiles default,myproject     # external_dirs + monitor wrappers
~/.hermes/shared-skills/extras/impeccable/sync_impeccable.sh        # optional: impeccable + overlay
```

`install.sh --help` lists the optional steps: Telegram menu pins, cron jobs from `extras/cron/` templates, and
disabling the fleet skills in project profiles. Update with `git pull`. Every profile reads the
folder live through `skills.external_dirs`.

Alternative: `hermes skills tap add <you>/hermes-shared-skills`, then `hermes skills install <skill>`
copies individual skills into a profile (hub-scanned, updated with `hermes skills update`).

## Layout

```
<skill>/SKILL.md (+ references/, scripts/)   one folder per skill = one command
shared/COMMON-CONTRACT.md                     contract several skills follow
extras/monitors/      cron monitor scripts (skip the model when nothing changed)
extras/cron/          cron prompt templates
extras/soul/          SOUL.md snippets every worker must see
extras/impeccable/    upstream sync script + Hermes overlay
extras/maintenance/   scratch_cleanup.py (weekly, no-agent cron; deletes worker scratch older than 7 days)
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
