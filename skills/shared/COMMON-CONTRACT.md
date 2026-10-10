# Shared skill contract

User instructions and repository rules define the authorized scope. Read the
relevant instructions, current source, tests and existing documentation before
changing their owners. Keep proposals distinct from accepted requirements and
implemented behavior. A skill invocation does not independently authorize source
changes, installation, publication, third-party contact or destructive actions.

Inspect status and preserve pre-existing edits, untracked files and live ownership.
Use [worktree isolation](WORKTREE-ISOLATION.md) when a separate writing checkout
is required. Do not reset, clean, stage or overwrite unrelated work. Keep secrets
and generated scratch out of deliverables.

Run the checks that discriminate the claimed change. Record actual commands,
results and the source they exercised; label missing coverage NOT_CHECKED.
Static policy checks and offline fixtures do not prove model adherence, native
worker execution, provider behavior or delivery. Review scoped diffs and links,
and reconcile affected documentation and task state without inventing evidence.
Report changed artifacts, verified behavior, limitations and remaining work.

Resolve helper paths from the actual loaded skill directory, not an assumed
Hermes home. Sibling bundled skills and this support directory retain their
relative layout. Quote absolute paths and repository arguments in shell commands;
`goals.py` examples mean `python3 "<skills-root>/repo-docs/scripts/goals.py"`.
See [plan handoff](PLAN-HANDOFF.md) for accepted backlog boundaries.
