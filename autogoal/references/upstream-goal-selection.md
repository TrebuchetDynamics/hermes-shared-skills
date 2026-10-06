# Read upstream before changing autonomous selection

## Procedure

Keep Hermes Agent/Desktop/Conduit read-only. Resolve the installed commit and upstream remote HEAD; pin raw-source reads to that upstream commit, saving snapshots outside the checkout. Compare the relevant files directly: a GitHub compare response may cap its file list at 300 and cannot establish that an omitted file is unchanged. Do not fetch/reset/pull or install a newer runtime merely to study it. Consult authoritative public documentation as well as code.

Trace these seams before attributing poor outcomes to the model or runtime:

- `hermes_cli/goals.py:run_kanban_goal_loop`: status-first exit, latest-response judge, continuation/finalize prompts, hard turn budget, unachievable blocking. A done verdict asks the worker to finalize; it does not prove a test passed. First response consumes one turn. Current observed implementation treats WAIT as CONTINUE in workers.
- `hermes_cli/cli_single_query.py:_run_kanban_goal_loop_q`: task identity and actual continuation wiring, not printed slash-command activation.
- `gateway/run_goals.py`: separate scheduled single-session goals; do not conflate with Kanban worker dispatch or `/goal` in the original thread.
- `agent/verification_stop.py:build_verify_on_stop_nudge`: suppresses prose-only edits; respects passing evidence; current observed guard bounds nudges with default max_attempts=2. Missing evidence triggers an actual check, never invented green status.
- `agent/verification_evidence.py:verification_status`: keyed by session and workspace; evidence before the latest recorded edit is stale. Command recognition and session identity can explain repeated verification independently of changed product behavior. Do not forge records or disable the guard.
- `cron/scheduler_delivery.py`: exact silence/routing behavior, independent from downstream completion. Preserve current configured delivery and local-only exceptions.

Separate selection quality from execution quality. Read all relevant profile homes read-only, with explicit session/message limits and current-session exclusion. Record selected candidates, disjointness, payoff, proposed checks, observed worker status, and exact artifacts. A silent picker alone proves neither no useful tasks nor a failed goal. A running worker is not complete. A title/body/receipt match is not a source-verified outcome.

## Selection and execution rules derived from the mechanisms

Write a concrete before/after delta and acceptance criteria before handoff, because the goal judge only sees the latest response and contract. Require acceptance evidence in the worker completion response without representing that response as independent verification. Compare meaningful candidates before expensive baselines; run only a focused safe reproduction when discovery needs it. Preserve scope-specific blockers and live ownership. After a passing check, advance to the next accepted dependency or disjoint useful task rather than endlessly re-auditing the same surface.

Treat incomplete contract fields as a preflight failure, not permission to enqueue a vague investigation. Structural checks cannot establish priority, truth, safety or owner approval. Keep native-tool and CLI handoffs under the same contract requirements and worker restrictions. Existing dispatched cards are not rewritten by a helper update.

## Observed upstream study

On 2026-10-04, installed `16bc0b6b94be7435cb63ed30923fbc7edd53f4c5` was compared with upstream HEAD `af90026aa09949579bd423d24def3d38f743cde0`. Direct raw-source comparisons found `hermes_cli/goals.py`, `agent/verification_stop.py`, `agent/verification_evidence.py`, and `gateway/run_goals.py` byte-identical. `cron/scheduler_delivery.py` differed by removal of `homeassistant` from the known delivery-platform allowlist; this does not concern the fleet's Telegram routes. These observations do not characterize all changes between commits and are not upgrade advice.

Stable sources:
- https://hermes-agent.nousresearch.com/docs/user-guide/features/goals
- https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
- https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/hermes_cli/goals.py
- https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/verification_stop.py
- https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/verification_evidence.py

Local receipts: `~/.hermes/cache/scratch/hermes_upstream_study/` (local, not in this repo). Secrets and profile credentials are never needed for this source study.
