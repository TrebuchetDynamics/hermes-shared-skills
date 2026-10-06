---
name: grill-me
description: Stress-test a plan or design in self-answer-first mode, and the questionnaire format agents use whenever they need the user (never block, ask). Use when the user says "grill me", wants plan gaps or hard decision pressure, or when work needs an owner answer. Do not use for glossary/ADR critique; use grill-with-docs.
---

# Grill Me

Stress-test the plan until only real owner decisions remain. Answer easy questions from evidence; ask one hard question only when the agent cannot safely decide.

## Quick start

1. Restate the plan or assumption being tested in one sentence.
2. List the hidden gaps internally: requirement gaps, design branches, risks, validation, rollout/order, and ownership.
3. Inspect available evidence before asking: docs, code, tests, git state, prior messages, and `codebase-map-understand.md` for cross-module plans.
4. Self-answer every easy question with evidence or a reversible default.
5. Ask one hard owner-decision question, with your recommended answer and consequence. If no hard question remains, state the assumptions and proceed.

## Channel-native questionnaire

When the user says "grill me", run an interactive interview, not a monologue or an evidence-pass status report. Inspect only enough evidence to ground the next question; do not let exhaustive research postpone the interview. Ask one decision question at a time and wait for the answer before asking a dependent question. If the plan/topic is absent, the first question asks what to stress-test.

Use the host's native question/clarification tool when available (Hermes: `clarify`). On Telegram, submit the question through that tool so the gateway renders its supported questionnaire/buttons; on other messaging channels or desktop, use the same tool and its supported native interaction. In the CLI, use its interactive clarification prompt. Do not manually send to another channel or invent a Telegram API integration. The session's channel determines delivery, not the profile name.

For a decision with clear options, put the recommended answer first in `choices`, with up to four choices. Keep options out of the question text. For an open-ended answer, omit choices. Include concise evidence and the consequence in the question when useful; do not require the user to read a separate template before answering.

If the tool is unavailable or the channel cannot render structured questions, ask one concise question in the current conversation and wait for a reply. If delivery fails, times out, is cancelled, or is skipped, do not treat that as an answer or acceptance. State the unresolved question and its recommended answer, and end the interview there. Outside an explicit "grill me" interview, use Questionnaire mode instead: never wait idle. After each actual answer, challenge the next unresolved branch until the owner stops or the plan has no material unresolved decisions. No live questionnaire is considered verified merely because this skill was updated.

## Questionnaire mode (whenever work needs the user)

Use this whenever an agent needs an owner answer during work: a decision, credential, sudo, review feedback or approval. Fleet rule: **ask, don't block.** Never pause a goal, park a card, or end a turn as "blocked / waiting for approval" because input is needed (see `hard-blockers`).

1. Finish all work that does not depend on the answer.
2. Self-answer everything evidence or a reversible default can settle. Only real owner questions remain.
3. Batch them, at most 5, the most consequential first.
4. **Live session with `clarify`:** one `clarify` call with `questions=[{question, choices}]`. Put the recommended choice first in each list, with 2–4 short choices. Put one line of evidence/consequence in the question text when useful.
   **No `clarify`** (cron, kanban worker, delivered report): end the report with this block:
   ```text
   Questions (no reply = defaults apply):
   1. <question> — A) <recommended> (default) B) <option> C) <option>
   2. ...
   Reply e.g. `1A 2B`.
   ```
5. Meanwhile: apply reversible defaults now and mark them "default applied, pending answer". For irreversible or red-line steps (money, deploy/publish, third parties, destructive data/history, secrets, sudo, credentials), prepare everything up to the final action and skip only that action.
6. A timeout or no reply is **not** acceptance of an irreversible step. For a reversible step, the applied default simply stands until the owner changes it.
7. Questions that outlive the turn go into BLOCKERS.md as entries (`hard-blockers` format, with `Default if no answer`).
8. Next run: read the replies (chat / `session_search`), apply them, and resolve the entries.

The turn's outcome is the work done plus the open questions, never "blocked".

## Operational basis

Use repo evidence before user questions:

- `git status --short --branch` and dirty-file ownership from the shared contract;
- README, task docs, issue/plan text, manifests, and relevant tests;
- live source for claims about current behavior;
- `codebase-map-understand.md` when the plan spans modules, then verify named files;
- `grill-with-docs` instead when the uncertainty is project language, glossary terms, ADRs, or documented decisions.

## Workflow

For each branch of the plan:

1. Name the branch and what it unlocks.
2. Separate evidence questions from owner decisions.
3. Resolve evidence questions by inspection or by a safe default.
4. Challenge the plan on blast radius, validation signal, ordering, rollback, data/security risk, and product intent.
5. Ask only the smallest remaining owner-decision or pivot question.
6. After the answer, summarize the resolved decision and move to the next dependent branch.

Do not ask checklist-style questions. Do not ask users to confirm facts the repo can answer. Do not brainstorm alternatives when one boring reversible default works.

## Skill contract

### Entry protocol

- Trivial: proceed directly and state the assumptions.
- Medium ambiguity: choose the safest baseline and ask only the missing hard question.
- High ambiguity/risk: ask about the owner decision, risk acceptance, irreversible direction, or pivot (Questionnaire mode), and keep doing the work that does not depend on it.

### Topology check

Before asking, confirm whether state/ownership, validation, blast radius, and ordering are clear. If one is unclear and evidence cannot answer it, that is the next question.

### Verification gate

A useful grilling pass ends with at least one of: a resolved assumption set, one answered hard question, a named pivot, an open question sent with its default, or a handoff to `grill-with-docs`, `prototype`, `tdd`, or implementation.

### Red lines

Do not make irreversible product decisions for the owner, approve irreversible or risky changes, or edit docs/code as part of an explicit grilling interview. In work mode, a reversible recommended default may proceed while its question is open; an irreversible step may not.

### Output contract

Use this compact shape when asking:

```text
Decision branch: <branch>
Question: <one hard decision>
Recommended answer: <default and why>
Consequence: <what accepting it unlocks or risks>
Evidence checked: <files/docs/tests/commands or none>
```

## Example

User: `grill me on this migration plan`

Agent: inspect the plan and repo evidence, self-answer rollout/test questions where possible, then ask the first irreversible sequencing or risk-acceptance question with a recommended answer.

## Shared contract

Follow [the shared skill contract](../shared/COMMON-CONTRACT.md) for repo study, dirty-worktree hygiene, verification evidence, safe handoffs, and safety defaults.
