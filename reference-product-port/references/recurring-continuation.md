# Recurring continuation

Use only when the owner requests scheduled autonomous progress.

1. Load scheduler guidance and inspect current schemas. List jobs first; update a matching job instead of creating a duplicate.
2. Persist a repo-local ledger with owner decisions, checkpoint, active file owners/handles, acceptance criteria, authority boundaries, next task and stop conditions. Fresh scheduled sessions cannot rely on conversation history.
3. Write a self-contained prompt with workdir/ledger path and policies for overlap, missed runs, retry, repeated-failure pause, output and completion. Scheduling is not proof of execution or uptime.
4. If activation needs checking, create paused, read back, resume on the authorized cadence and read back again. Record actual ID/state.
5. Respect the occurrence execution budget. Do not rely on process-local delegated children surviving its exit. Durable execution needs a supported mechanism, captured handle and cleanup owner.
6. Never steal active-lane files or overlap Flutter/build commands. While ownership is active, do independent read-only discovery or record the blocker. After release, claim one exact scope before mutation; append observed evidence and next action afterward.
7. Skip missed ticks and avoid same-tick retries unless required. Distinguish expected waiting for an active owner from an execution failure; do not count ordinary ownership waits as failing implementation attempts. Pause on repeated failures or missing authority/auth provisioning; do not broaden privileges or substitute the chosen provider/model to evade blockers. A blocked native stage does not authorize package installation or prevent independently approved source/browser work.
8. At producer completion, update the ledger immediately with released scopes, resolved findings and the next bounded task; stale ownership can keep every scheduled occurrence idle. Read scheduler state rather than assuming a previously enabled job remains active. If it self-paused, inspect its last output, resolve or narrow the blocked scope, revise the checkpoint/policy and then resume under existing authorization; read back enabled state without claiming a post-resume occurrence ran.
9. Verify occurrences through run records/receipts; distinguish scheduled, running, completed and blocked. Prefer local output when frequent updates would spam chat; report milestones and owner-only blockers through the requested channel.

Cron starts fresh sessions; it does not keep the original process permanently awake. Pause at milestone completion or obtain new approved scope rather than converting an enduring product goal into unlimited unrelated work.
