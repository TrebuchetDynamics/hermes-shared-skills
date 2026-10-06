---
name: fleet-blockers
description: Use for /fleet-blockers — read-only list of verified user actions (credentials, sudo, decisions) aggregated from every project repo BLOCKERS.md.
version: 0.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [fleet, blockers, coordination]
    related_skills: [hard-blockers, fleet-governor, fleet-status]
---

# Fleet Blockers

## When to Use

Use `/fleet-blockers` in the default governor profile to build the human-action queue from canonical repository BLOCKERS.md files. This command is read-only. It does not create files, edit tasks, resolve blockers, restart workers or alter schedules.

## Procedure

1. Load `hard-blockers`. Compare `~/.hermes/fleet-governor/repositories.json` against current configured profile workspaces. Check exact Git roots and documented monorepo conventions. Refresh a stale registry only in an authorized maintenance/recovery run, not this read-only command. Report missing/stale coverage as UNKNOWN. Exclude upstream/vendor reference repositories.
2. Run the read-only collector:

   `python ~/.hermes/shared-skills/fleet-blockers/scripts/collect.py --registry ~/.hermes/fleet-governor/repositories.json`

   Collector output is recorded candidate entries plus structural issues, source hashes and coverage. It never attests semantic validity, authority or autonomous exhaustion. An empty file does not prove historical gates disappeared.
3. For each recorded ACTIVE candidate, re-evaluate current evidence, prior user instructions/decisions, task scope and lifecycle, tools/user-space options, other project workers and fleet capabilities. Ensure only mandatory USER_INPUT, SUDO or USER_DECISION remains and the user action is minimal/exact. Do not run production, sudo, credential or destructive operations to test a claim. Do not equate a field timestamp with fresh verification.
4. Recheck source hashes immediately before presenting the queue. Changed files require a new read, not stale output. Deduplicate repository plus condition, preserve IDs/provenance; IDs are unique within a repository, not globally. Duplicate/malformed/stale entries and incomplete investigation go in a separate reconciliation/UNKNOWN section, not the verified user queue. Never silently resolve active entries.
5. Present the result as a questionnaire (`grill-me` Questionnaire mode): each item is a numbered question with lettered options, the `Default if no answer` marked, and what is already proceeding on it. Present only verified irreducible dependencies, ordered PROJECT_BLOCKING, SCOPE_BLOCKING, ADMIN_BLOCKING. Show only repository, BLK ID, category, impact, exact decision/input/sudo action, and one-sentence consequence of waiting per item. Impact is informational: PROJECT_BLOCKING means no valuable work on the current milestone can proceed; SCOPE_BLOCKING means only a feature/slice is blocked; ADMIN_BLOCKING means governance/documentation/lifecycle is blocked but product work can continue. Use the verified canonical Impact field or establish it from current milestone evidence; do not infer whole-project blocking from a blocked card. Missing/disputed verification stays agent-owned and OUTSIDE the user-action queue. Generate actions from canonical fields, never task-state speculation. Disclose coverage/inspection limits without asking the owner to investigate them. If no entry verifies, distinguish zero verified from zero recorded.

An entry in the final queue attests: nothing further agents can legitimately do will remove this dependency without the owner's action. Category describes the immediate next dependency: a choose/schedule-or-park action is USER_DECISION; USER_INPUT applies only AFTER the resource path is selected and only the owner can supply it. Expired per-sweep budgets, ordinary failing checks and internal lifecycle states do not create user authorization requirements. This read-only command diagnoses sanitation needs; explicitly authorized governor reconciliation moves invalid ACTIVE entries to Resolved with original history, updates exact linked cards, routes admitted autonomous work and verifies the observed worker. Never silently delete an entry or manufacture its replacement.

For genuine new/legacy hard blockers, the authorized governor recovery workflow first updates the canonical file and references its ID in the actual card through supported tooling, verifies that write, then aggregates. This read-only command reports required reconciliation; it never writes simply to satisfy the policy.

## Verification

Run `python ~/.hermes/shared-skills/fleet-blockers/scripts/test_collect.py` for collector regressions. Structural checks are not semantic validation. Entry-local defects in resolved history must not hide unrelated valid ACTIVE entries: keep the candidates and report the history issues. Structural ambiguity and duplicate IDs fail closed. Installation does not prove future fleet behavior or live gateway command registration.
