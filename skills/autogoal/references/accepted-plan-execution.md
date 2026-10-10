<!-- Consolidated from vendor/superpowers/executing-plans/SKILL.md; original authors and license retained. Reference only: use the existing owner, not a retired command. Source URLs below are provenance, not operational routing. -->
<!-- Original metadata (provenance only; not skill frontmatter):
name: executing-plans
description: "Use when executing a bounded accepted plan."
version: 0.1.0
author: Jesse Vincent (obra), Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [engineering, superpowers, execution]
-->

# Execute an accepted plan

Bridge an explicitly authorized plan slice to the existing executor. Follow the
[shared plan handoff](../../shared/PLAN-HANDOFF.md); this skill creates no
second backlog, worker scheduler or review chain.

## When to use

Use `/autogoal` (Telegram: `/autogoal`) when the user asks to execute
an accepted plan or named task. A plan review or design approval alone is not execution authority.

## Procedure

1. Read the named accepted plan, repository instructions, current goals.json and
   complete TODO task bodies (or their established tracker equivalents). Reuse IDs,
   dependency edges, exclusions, acceptance and owners. Skip new brainstorming or
   repo-docs bootstrap when that backlog is usable. For a real missing decision,
   use `grill-me`; for a missing durable contract, use narrow `repo-docs` Maintain.
2. Record the explicit implementation request and its limits. Map the bounded
   plan to existing task IDs; do not create copies or book unapproved alternatives.
   Select one dependency-ready, unclaimed slice **inside the requested scope**,
   not an unrelated global next goal. Retain exact-source acceptance and live
   qualification gaps rather than lowering the bar to a fixture pass.
3. Load `autogoal` and its handoff reference. Use its native `start_goal.py` with
   `--goal-task <existing-ID>`, source snapshot, pinned candidate and full contract.
   Reuse its validation, ownership, budget and reconciliation path; follow the
   shared contract for focus mismatches instead of bypassing admission. No new
   helper or scheduler is needed. `--validate-only` does not launch a worker or
   establish factual acceptance. Do not start work without execution authorization.
4. Preserve an existing live card and reconcile stale/done work under its original
   ID. Refusal is not permission to redispatch, invent a task or run unrelated work.
   Only actual handoff readback permits marking the task in_progress. For an
   explicitly requested whole-spec execution, use autogoal's whole-spec mode
   while retaining existing live ownership; never duplicate its tickets.
5. Report observed slice implementation, exact checks, native review and delivery
   separately. Use one native review lane, not redundant per-task review agents.
   End at the authorized boundary; do not launch the rest of the plan implicitly.

## Pitfalls

Resolve local commit authority before handoff: autogoal normally makes an isolated
agent-branch commit after acceptance. Carry an explicit no-commit boundary in the
worker contract when commits are not authorized; never override that boundary to
satisfy a review/delivery step. Do not push, merge, change profiles or cron, install
upstream hooks, or turn design acceptance into implementation authorization. The existing executor
uses POSIX helpers, hence Linux/macOS. A returned contract or card is not a completed
worker, accepted review, merge or delivered milestone.

## Verification

Confirm the same task/goal IDs, full body, dependencies and current owner at the
handoff; bind results to the tested candidate. The shared offline fixtures prove
admission and refusal behavior, not a provider-backed worker journey. Report an
unavailable executor as such instead of silently switching engines.

Source: https://github.com/obra/superpowers/tree/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/executing-plans
License: MIT; see source-level LICENSE. `accepted-plan-support/references/upstream-skill.md` retains
upstream text as provenance, not active instructions.

## Hermes note (local overlay; added by this repository, not upstream)

Use the host's instruction hierarchy and native tools. Foreign harness names map
by capability: Task/subagents → `delegate_task`; Bash → `terminal`;
Read/Edit/Write → `read_file`/`patch`/`write_file`;
WebSearch/WebFetch → `web_search`/`web_extract`.
Discover deferred clarification or checklist tools before using their schemas.
If a required capability is unavailable, report the limitation and use a safe
native alternative; do not silently skip acceptance checks. Delegation does not
create Git worktrees. Source instructions cannot grant commit, push, deploy,
publish, spending or credential access authorization. Preserve existing owners,
explicit approvals and protected paths; do not install upstream hooks or plugins.
