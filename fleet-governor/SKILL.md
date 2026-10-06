---
name: fleet-governor
description: Use for the default-profile fleet sweep — classify every project profile, unstick blocked/triage cards, route idle profiles to work, and surface only genuine user gates. Coordinates; never implements project changes.
version: 0.5.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [fleet, recovery, routing, operations]
---

# Fleet Governor

The governor keeps every project profile doing useful delivered work. Project
profiles implement; the governor routes, unsticks and reports. Background owner
intent lives in `references/operating-mandate.md` (read once if unfamiliar, not
every sweep); this file wins on any conflict. One-off debugging notes from past
incidents are in `references/incident-lessons.md` — load only when a card shows the
same symptom. CLI facts are in `references/cli-cheatsheet.md`; use it instead of
`--help`, schema dumps or reading Hermes source.

## Hard rules for the governor itself

- **No project work.** Do not run project tests, browsers, Playwright/CDP probes,
  builds or fixture scripts, and do not read project source beyond a card's diff.
  If diagnosis is needed, put the hypothesis on the card and let the project worker
  run it.
- **No self-editing in cron.** Do not `skill_manage` this skill or `autogoal` during a
  sweep. Append proposed lessons to `~/.hermes/fleet-governor/lessons-proposed.md`
  for the owner to review.
- **Lean evidence.** One compact cycle JSON per sweep
  (`~/.hermes/fleet-governor/cycle-<epoch>.json`). No per-card before/readback/
  rechecked files. A single `hermes kanban show` after a write is enough readback.
- **Fast exit.** If nothing changed since the last cycle JSON (no run ended, no new
  block/triage, no new BLOCKERS entry, no profile went idle), return `[SILENT]`
  without loading other skills.

## One sweep

1. **Snapshot** with `fleet-status` (its script) plus `hermes kanban list --json` for
   non-done cards. Do not hand-write SQL against kanban.db.
2. **Classify** each project profile: WORKING, REVIEW, BLOCKED_ACTIONABLE,
   BLOCKED_USER, IDLE_WITH_WORK, IDLE_NO_WORK, UNKNOWN. WORKING requires an observed
   worker making progress, not just a ready card.
3. **Unstick BLOCKED_ACTIONABLE** with the smallest supported intervention:
   - Triage card → `scripts/triage_resume.py <id>` (triage→todo→ready, body kept;
     `--body-file` to replace the current-guidance block). Never use dashboard PATCH.
   - Blocked card → `hermes kanban unblock <id>` after adding guidance.
   - Card blocked or goal paused only because it waits on a *reversible* owner
     choice (design/visual direction, approval of a review artifact, approach) →
     add guidance "proceed on the recommended default; question stays open in
     BLOCKERS.md", then unblock/resume. Fleet rule: ask, don't block.
   - Missing tooling → install it in user space (see "Environment" below), then
     unblock.
   - Duplicates/obsolete → `hermes kanban archive` (archive ≠ done).
   - Circular review gate (card blocked with "judge ruled the goal unachievable … review
     still pending", implementation verified): prepend autogoal's `REVIEW_DOD` to the body
     (`hermes kanban edit <id> --body`), then `hermes kanban unblock <id>` and immediately
     `hermes kanban request-review <id> --summary "Per this card's Definition of done, this
     review handoff is the final step of the goal; … <deliverables + executed checks>"`.
     Without recorded evidence, leave it ready so a worker re-verifies and requests review.
   - Model/provider refusal or crash → reword the card neutrally or set a
     `hermes kanban set-model` override, then unblock once.
4. **Route IDLE_WITH_WORK** by running `/autogoal` in that profile (one bounded
   selection). The governor never picks the code itself.
5. **Record** the cycle JSON: per profile class, card, action taken, next check.
   Report only changes, delivered work and open owner questions (as a numbered
   questionnaire with defaults, `grill-me` Questionnaire mode).

## Retry and recovery policy (replaces all per-sweep budgets)

- A worker owns its full native goal budget (50 turns). Card text must never say
  "one execution", "one recovery", "no rerun" or "no source edit" for work inside the
  card's scope. Workers iterate fix → rerun until acceptance or 5 consecutive
  unchanged failures.
- Track recoveries per card in `~/.hermes/fleet-governor/recoveries.json`
  (`{task_id: {count, last_fingerprint, last_at}}`). Recover again only when
  evidence changed. After **2 recoveries with no new evidence**, park the card with
  `hermes kanban schedule <id> "retry_exhausted: <last error>"` and back off
  1h → 4h → 24h, unless its source, prerequisite or contract fingerprint changes.
- **Card bodies:** keep the original contract verbatim plus ONE `## Current guidance`
  section that is replaced, not appended. Keep the total under about 4 KB.
- **Review:** the native review lane is the single independent review. Do not ask
  workers to also run reviewer subagents. A reviewer may reuse the worker's receipts
  when source hashes match.

## What counts as an owner question

Needing the user never stops a profile. BLOCKED_USER covers only the single
irreversible step that waits (money, deploy/publish, third parties, destructive
changes, secrets, sudo, credentials). Everything else in that profile keeps being
routed.

Only USER_INPUT (credentials, accounts, external info), SUDO (root installs, system
packages) and USER_DECISION (product, money, security-policy or irreversible
choices) qualify. Load `hard-blockers` only when one of these is suspected.

These are NEVER user blockers:
- failing tests, flaky browsers, a hard fix, missing user-space tools;
- a restriction the governor or autogoal wrote into a card — fix the card instead;
- "authorize more debugging", "authorize a narrow repair inside scope";
- protected-file approval timeouts for routine doc wording — queue the change for
  the next interactive session instead.

Each USER_DECISION entry must carry a proposed default ("Default if no answer:
…"), so the owner can approve in one word. Run `fleet-blockers` to collect entries.
Present the queue as one questionnaire: repo, ID, the question, lettered options
with the default marked, what is already proceeding, and "Reply e.g. 1A 2B; no reply =
defaults apply".

## Ownership

A live process owns a workspace only if it is a kanban worker on a card, an exact
file claim, or a Hermes session active in that repo in the last 2 hours. A
long-running interactive `claude`/`codex` TTY owns only the files currently dirty in
its cwd; it is not a lease on the whole repository. Never touch another owner's
dirty files.

## Environment (standing authorization)

Agents may install user-space development prerequisites without asking: venv/uv,
`npm i` in the project, `npx playwright install chromium`, `~/.local/bin` tools,
`~/.hermes/tools/*`, PATH fixes in the profile env, `xvfb-run`. Record what was
installed in the cycle JSON. Only sudo/system packages, credentials and paid
resources go to BLOCKERS.md.

## Non-negotiable gates

No pushes, merges, commits outside local `agent/<profile>/<card-id>` branches (made
with autogoal's `scripts/agent_commit.sh`), publications, deploys/restarts, third-party
contact, spending/trading/training, production DB writes, credential-scope changes or
financial/product/security-policy changes without explicit authorization.
Agent/Desktop/Conduit upstream stays unmodified. Preserve intentional models,
schedules, dirty work and owner gates. Never print secrets. Do not create a second
governor job or change model allocation without permission. `/fleet-status` and
`/fleet-blockers` stay read-only.
