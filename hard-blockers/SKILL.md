---
name: hard-blockers
description: Use when something needs the user (credential/info, sudo, or a product/money/security decision) or when maintaining BLOCKERS.md. Needing the user means asking a questionnaire and continuing, never stopping. Not for failing tests, missing user-space tools or hard engineering.
version: 0.2.0
license: MIT
author: Hermes Agent
metadata:
  hermes:
    tags: [coordination, blockers, fleet]
    related_skills: [grill-me, repo-docs, fleet-governor]
---

# Hard Blockers — BLOCKERS.md

## When to Use

Use when you are about to report that work needs the user, when maintaining BLOCKERS.md, or for fleet human-action aggregation. Ordinary work does not need this skill; if a repository has a root BLOCKERS.md, just respect its active entries.

## Ask, don't block (fleet rule, overrides anything older)

Needing the user is a **question, never a stop**. No agent pauses a goal, parks a card, ends a turn or reports "blocked / waiting for your approval / gated on review" because user input is needed. Instead:

1. **Finish everything that does not depend on the answer first.**
2. **Ask a questionnaire.** Follow the `grill-me` skill's *Questionnaire mode*: with `clarify` available, send up to 5 questions in one call, each with 2–4 choices and the recommended choice first. Without `clarify` (cron, kanban workers, delivered reports), end the report with a numbered `Questions` block. Each question has lettered options, the recommended one marked, and the line "Reply e.g. `1A 2B`; no reply = defaults apply".
3. **Keep moving until answered:**
   - **Reversible choice** (design direction, visual taste, naming, scope order, which fix first, implementation approach): apply the recommended default now. Mark it "default applied, pending your answer" and keep it easy to revert.
   - **Irreversible or red-line action** (spending money, deploy/publish/release, contacting third parties, destructive data or history changes, secrets, sudo, credentials): skip only that final action. Prepare everything up to it, so the answer triggers just the last step. Continue all other work and re-ask in the next report.
4. **Record** questions that outlive the turn in BLOCKERS.md (format below), with `Default if no answer` and whether the default was applied.
5. **Read answers back** at the start of every run (chat history / `session_search`, BLOCKERS.md). Apply them and move the entry to Resolved.

Approval of a review artifact (contact sheet, screenshot, plan, design) is never a gate. Pick the evidence-backed direction, implement it on reversible terms, show the result, and ask for feedback in the same report.

Final reports lead with what was done, then `Questions (defaults applied: …)`. Never make "blocked", "paused", "waiting for approval" or "gated" the outcome of a turn: the goal judge pauses goals on that wording.

## What BLOCKERS.md is

BLOCKERS.md is the repository's **open-questions ledger for the owner**. It holds only questions that agents cannot answer from evidence. Recording an entry never stops work: it is paired with a questionnaire and, where reversible, a default already in effect.

Use one repository-root BLOCKERS.md per project repository. Create it only when recording a real entry (or during an authorized repo-docs Bootstrap); do not create files just to satisfy this policy. In a monorepo, use its repository-root file unless an existing documented project-level convention explicitly applies. Do not create competing blocker files elsewhere. Do not modify read-only upstream/vendor reference repositories to install this policy.

## Only three categories

A question belongs in the ledger only when the answer is something the agent cannot legitimately supply itself:

- USER_INPUT: information only the user can supply, a required credential/token, unavailable required file/account/external resource/value, or clarification that repository evidence, prior instructions and project records cannot establish. Do not record secret values. Request credentials through the supported secret-safe mechanism, not ordinary chat or this file.
- SUDO: a genuinely necessary root/sudo operation with no safe user-space or already-authorized alternative which the agent can complete. Include the narrow exact command when safely known. Never request broad sudo bash operations when a narrower action suffices.
- USER_DECISION: materially different valid choices remain and evidence does not select one. Proceeding would decide product behavior, compatibility, meaningful architecture tradeoffs, destructive migration, security, finances, operations, publication/release, ambiguous work ownership, or additional scope for the user. State options and consequences briefly. Recommend only when evidence supports it. Routine implementation choices under accepted requirements are not user decisions. A binding explicit user-only authorization gate also requires the user; cite the exact restriction, without inventing a second choice.

These are the only categories. A design choice is USER_DECISION, not USER_INPUT.

Every entry must include `Default if no answer:` with the option the agent recommends, so the owner can reply with one word. When the default is reversible, it is **already applied** (`Proceeding with:` says so); it is not held back waiting for confirmation. USER_INPUT and SUDO have no default for the missing value itself. Work around it, keep all other scope moving, and state exactly which single step waits on it.

## Not hard blockers

Do not record autonomously investigable or resolvable engineering problems: failing tests, compiler errors, bugs, dependency conflicts, non-privileged missing tools or browser binaries, unclear code, dirty ownership discoverable from evidence, review feedback, decomposition, packaging/build/lint failures, temporary network failures, stale generated files, missing docs, authorized merge conflicts, uncertainty further inspection can resolve, difficult/expensive/long work, turn limits, not knowing the next step before investigation, or work routable to another capable profile.

Also never blockers:
- A restriction an agent, the governor or autogoal wrote into a card ("no source edit", "one rerun", narrow scope). Fix the card contract instead.
- Requests to "authorize" more debugging, another test run, or a narrow repair inside the card's scope.
- A protected-instruction-file approval prompt that timed out in an unattended run for routine wording. Note it in TODO for the next interactive session.
- Requests to commit finished work. Agents commit to local `agent/<profile>/<card-id>` branches themselves; only merging/pushing is the owner's, and that is a normal review handoff, not a blocker.
- A goal-mode `needs_input` block forced only because `transient` is not accepted; that is internal.

This file is not a TODO list, bug tracker, risk register or a reason to stop. Waiting for workers, pending automated review, capabilities the governor can provide and retriable infrastructure remain in the task system unless they genuinely require one of the three user actions. A blocked task/card can coexist with an empty BLOCKERS.md.

## Before declaring

Make a reasonable autonomous effort. Check applicable repository docs, AGENTS.md, BLOCKERS.md, card/task history, Git history/diffs, configuration, installed tools, user-space alternatives, tests, previous user instructions, receipts/logs and other profile capabilities. Do not ask what evidence already answers. Do not perform speculative or unsafe actions to avoid a legitimate blocker.

Before SUDO, check local installation, repo-local tools, containers, compatible installed executables, isolated fixtures and non-root configuration. Do not weaken security or touch production as a workaround.

Before USER_DECISION, search PRDs, ADRs, specs, accepted cards, prior user decisions and Git history. An agent's implementation or proposal is not proof of accepted intent.

## Canonical structure

Initialize an absent file, when authorized to write in the repository, exactly as:

```markdown
# BLOCKERS

This file contains only open questions for the owner. Agents keep working while these are open.

## Active

None.

## Resolved

None.
```

An empty file is valid. Never invent an entry to fill it. Explicit read-only/Audit requests remain read-only, including this file; report its absence for the next authorized maintenance pass.

Use unique IDs within the canonical file. Check existing active and resolved IDs immediately before allocating BLK-YYYYMMDD-NNN. Preserve concurrent changes and reread before a write. Duplicate IDs across repositories are qualified by repository, never globally conflated.

Active entry:

```markdown
### BLK-YYYYMMDD-NNN — Short title

- Status: ACTIVE
- Category: USER_INPUT | SUDO | USER_DECISION
- Owner: user
- Task/Card: identifier or N/A
- Blocked scope: exact work that cannot continue
- Why blocked: concise factual explanation
- Evidence: repository paths, observed command output, task receipts or concrete evidence
- User action required: one precise action or answer (phrased as the questionnaire question)
- Default if no answer: the recommended option
- Proceeding with: what the agent is doing meanwhile (default applied / everything except <final step>)
- Asked: channel and date the questionnaire went out
- Resume condition: the answer or input that completes the remaining step
- Created: ISO-8601 date/time when available
- Last checked: ISO-8601 date/time when available
```

Use one actual category, not the alternatives literal. Dates are observations, not fabricated timestamps. Use unavailable if time is genuinely unavailable.

Resolved entry:

```markdown
### BLK-YYYYMMDD-NNN — Short title

- Status: RESOLVED
- Category: USER_INPUT | SUDO | USER_DECISION
- Resolved: date/time
- Resolution: what changed
- Evidence: evidence that the blocker is no longer active
```

Entries must be specific, minimal, actionable, evidence-backed and understandable without the agent conversation. User action must be the smallest concrete action, never 'fix this' or 'help with Flutter'. Cite exact resources and restrictions. For multiple options, explain their consequences briefly.

## Maintenance and completion

Avoid duplicate conditions; update the existing entry. Add only genuine newly established hard blockers. Change Last checked only after actual re-evaluation. Preserve unrelated entries and useful resolution history. Never silently delete an active entry.

When evidence shows resolution, move the entry immediately from Active to Resolved. User statements establish decisions/input, but verify technical effects when verification is possible before resolving. Preserve its ID.

When something needs the user:
1. Record/update the canonical entry, including `Default if no answer` and `Proceeding with`.
2. Reference its ID in the actual task/card through supported tooling (N/A only when no task/card exists). Verify the exact card write by reading it back. Do not move the card to blocked for a reversible question.
3. Send the questionnaire (`grill-me` Questionnaire mode) in the same turn.
4. Continue: apply reversible defaults, prepare irreversible steps up to the final action, and keep all independent scope moving.
5. Report what was done, then the open question IDs with their defaults.

Without an entry, do not describe work as waiting on the user. Missing evidence or incomplete inspection is internal investigation, not a user question.

## repo-docs

Treat BLOCKERS.md as an additional operational coordination document. It does not replace README, PRD, ADRs, spec, test-plan, runbook, CHANGELOG or TODO. Create it when absent during authorized Bootstrap/Maintain. Preserve structure; detect duplicates/stale entries; reconcile resolutions only from evidence. No manufactured entries or stale date bumps. Audit/read-only reports findings without changing it.

## Fleet governor

Aggregate canonical repository files, never independently invent a human-action section from task states or prior summaries. Before presenting each recorded active entry, verify it still exists, no project agent can resolve it, no fleet capability can resolve it, existing evidence does not answer it, and the requested action is minimal/explicit. Reconcile newly verified genuine legacy gates into the file and task first. Unknown/stale/unverified entries require investigation and are reported separately from a verified user queue; an empty newly initialized file is not proof no real gates exist.

Deduplicate by repository and blocker condition while retaining IDs/provenance. Never silently resolve user-only authority. Present them as one questionnaire: repository, ID, the question, options with the default marked, and what is already proceeding. Continue independent work. Installation of this policy does not prove future agent adherence.
