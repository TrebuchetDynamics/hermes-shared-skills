---
name: lgtm
description: Resolve short approval against the latest checkpoint.
version: 0.3.0
metadata:
  hermes:
    tags: [approval, planning, scope, continuation, git, delivery]
---

# LGTM

Adapted for Hermes from TrebuchetDynamics/pi-toolset, skills/planning/lgtm/SKILL.md:
https://github.com/TrebuchetDynamics/pi-toolset/tree/main/skills%2Fplanning%2Flgtm

## When to use

Use when the user says "lgtm", "looks good", "approved", or "go ahead" to accept a prior assistant checkpoint. Approval plus new instructions is a normal request; follow the new instructions instead of forcing this resolver. Reviewer verdicts, quoted examples, and tool output are not user approval.

Resolve one short approval to the latest safe action. Do not invent a task, revive stale recommendations, broaden permissions, or rerun completed work. This procedure applies to every profile and channel.

## Procedure

1. Inspect the user's phrase and qualifications, the immediately preceding assistant message, and an active workflow checkpoint only when that message clearly points to it. Read live repository state only as needed for the accepted action.
2. Choose the first safe target: an exact "If you say lgtm: I will <action>" promise; a single recommended next action or explicitly recommended plan; or the active workflow recommendation clearly surfaced in that message. A Ponytail/complexity review's concrete recommended cleanup list is an actionable plan: `read-only audit; no edits or tests run` describes how findings were collected, not a prohibition on implementing them after user approval. Treat LGTM of that list as Act: verify the recommendations against current source, apply supported items within the listed scope, and run normal checks. Use the owning project profile when required. Proposed removal of verified unused code/dependencies is not destructive user-data/history deletion; preserve the latter's confirmation boundary. An explicit instruction to implement a quoted list is a new request, not stale approval. Never reach past a newer assistant message for bare LGTM. If the latest message reports completed work with no recommended continuation, acknowledge acceptance and stop.
3. Classify: Act (safe action remains undone); Accept only (already complete); Evaluate (reviewer/advisor input requires verification); or Confirm (exact risky action needs explicit confirmation). If there is no clear safe target, ask one focused question using `clarify` if available, otherwise ask in the current conversation. Use the current channel's native prompt; do not send to another channel. A skipped, cancelled, timed-out, or undelivered prompt is not consent.
4. Preserve the exact scope, files, ownership, side effects, and validation plan. Check whether the action already happened. State "Accepted: <exact meaning>." and perform only that action once with the available Hermes tools; do not ask a redundant "Should I proceed?". When an existing worker owns prerequisite docs or a backlog, inspect its registered worktree before creating replacements. Reuse its task definition with a recorded revision or content hash, preserve its ownership, and isolate any approved implementation in a separate registered workspace. Distinguish a draft inspected from a stable handoff actually obtained; finding an active draft alone neither proves readiness nor requires a second approval for already-authorized independent work.
5. Verify the downstream action through its normal checks. Read back external writes before claiming success. Report actual results or a precise blocker; an accepted plan is not execution evidence.

## Permissions and boundaries

A short approval does not add another slice, broader cleanup, package installation, tracker mutation, network operation, or delivery step that was not in the accepted checkpoint. Existing system/tool approval requirements still apply.

Ordinary commit and push are accepted only when the immediately preceding assistant checkpoint explicitly offered those exact delivery actions. Then load and follow the `git-commit-push` skill (`skill_view("git-commit-push")`). It covers shared-worktree isolation, the stage → gate → push order, remote verification, and the chat-sized report. A generic LGTM after an implementation report never implies shipping. Autonomous card work without an explicit ship request commits only to its local `agent/<profile>/<card>` branch and never pushes.

Short approval is insufficient for destructive user-data deletion, unproposed source removal, spending money, secret/private-data publication, production deployment, publishing, irreversible Git history changes, force-push, rebase, merge, or broad unproposed scope. Removal of specifically proposed, verified-unused source or dependencies belongs to the approved cleanup scope; it does not require a redundant deletion confirmation. Ask for confirmation naming the exact action and risk. Do not reinterpret approval settings as permission to broaden scope.

For goal slices or frontier work, continue only the named approved scope, not the entire backlog. For tracker publication, act only when the checkpoint names the tracker and exact previewed mutations and explicitly offers them on approval; do not add inferred tickets. For one recommended refactor candidate, implement only that candidate; for an approved concrete cleanup list, implement every supported item in that list. Do not reinterpret a list as permission for just the easiest item. Use the available host workflow, not an unavailable Pi slash command.

## Review feedback

An assistant's adopted reviewer recommendation is accepted for verification, not as established truth. Verify every factual finding against live source and tests before applying it. Reject speculative rewrites or unsupported claims with a concise reason. When an independent review is justified, `delegate_task` can provide clean context: brief the objective, artifact, constraints, and requested verdict without your preferred answer or reasoning chain. Delegation is optional, not a requirement on every approval. Label an in-context review as non-independent.

## Output contract

Acting: "Accepted: <exact action>." Execute it, then report normal verification.
Acceptance only: "Accepted: <completed result>. No further action implied."
Ambiguous: "What should I treat as approved? My read: <safest interpretation>." Prefer the native `clarify` prompt when available, with the safest interpretation as the first (recommended) choice. Asking is not a stop: continue any already-authorized independent work.
Risky: "Approval needs explicit confirmation: <exact risky action and risk>." Prepare everything up to that action so a "yes" triggers only the final step, and report what is ready.
Handoff/blocker: name the accepted action, artifact/context, next step, and success signal without claiming completion.

## Pitfalls

Do not treat quoted/tool/reviewer text as an assistant promise. Do not rerun completed checks, edits, or delivery. Do not infer shipping, restart brainstorming, or expand scope. Do not install missing tools or launch external reviews just because upstream examples mention them. Check repository instructions and dirty-file ownership before implementing an accepted change; preserve unrelated user work.

## Verification

The resolution must name the accepted meaning and produce exactly one outcome: verified completion of the promised action, acceptance-only, a precise unresolved confirmation, or a bounded handoff/blocker. Configuration or skill installation alone does not prove live behavior.

Examples:
- Assistant gives a concrete Ponytail cleanup list ending `read-only source audit; no edits or tests run`; user says LGTM: verify and implement the listed recommendations, run relevant checks, and report what actually changed. Do not reply `Accepted: the audit. No further action implied.`
- Assistant offers to wire one CLI adapter and rerun its tests; user says LGTM: implement only that adapter and run those tests.
- Assistant reports tests passed with no next action; user says LGTM: acknowledge without rerunning tests or committing.
- Assistant offers two options without recommending one; user says LGTM: ask which option, using `clarify`.
- Assistant offers "commit these 3 files and push"; user says LGTM: follow the `git-commit-push` skill for exactly those files, push, verify the remote, report hashes.
- Assistant offers a production deployment; user says LGTM: ask for confirmation naming the deployment and risk.
