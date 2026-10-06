# Clean-Context Delegation

Use this contract whenever a skill wants a second opinion from an **advisor** or
**reviewer**. The value of these roles comes from *unbiased, clean context* — a delegate
that has not seen the main agent's reasoning and therefore will not rubber-stamp it.
Treat this as a baseline; a skill's own instructions win if they are stricter.

## Roles

- **Advisor** — strategic/architecture/product second opinion on a *plan or decision,
  before execution*. Use for high-leverage or cross-cutting decisions (architecture
  seams, ownership, product trade-offs). Skip for small reversible choices the repository
  evidence already settles.
- **Reviewer** — code quality / security / UX second opinion on *changes, after
  execution*. Use before completion or ship on non-trivial diffs.

## Clean-context briefing

When you delegate, brief the delegate with:

1. the objective,
2. the artifact under review (the plan, or the diff plus its intent),
3. the relevant constraints, and
4. the exact verdict you need back (for example "name the top risk and one alternative",
   or "list correctness, security, and UX findings").

Do **not** include your own justification chain or your preferred answer. That is exactly
what biases the delegate toward agreement and destroys the point of a clean context.

## Consuming the verdict

- The verdict is advisory. Never blind-apply it.
- Verify every codebase claim against live source before acting on it; when a finding
  depends on cross-module impact and `codebase-map-understand.md` exists, use it for
  caller/path leads and verify them in source.
- Reject speculative edge cases, broad rewrites, and over-complicating fixes with a
  concise reason.
- If the delegate and the main agent disagree, surface the trade-off. Ask the smallest
  owner-decision question only when repository evidence does not resolve it.

## Capability degradation

- **If the host exposes a clean-context dispatch tool** (a fork, subagent, or task tool):
  spawn one delegate with a clean context and the briefing above. This is the preferred
  path.
- **Otherwise:** run a single role-lens pass in the current context **and say so** —
  label it explicitly as an in-context lens that lacks context isolation, so the user
  knows it is the weaker fallback. (`grill-with-docs` council mode documents the
  local-lens form.)
- Never present an in-context lens as if it were a clean-context second opinion.

## Scope guardrails

- Delegation is opt-in and risk-justified, not mandatory on every action.
- The reviewer does not run nested reviewers or reviewer panels by default; panels remain
  opt-in (consistent with `autoreview`).

## Shared contract

Follow [the shared skill contract](./COMMON-CONTRACT.md) for repo study, dirty-worktree
hygiene, verification evidence, safe handoffs, and safety defaults.
