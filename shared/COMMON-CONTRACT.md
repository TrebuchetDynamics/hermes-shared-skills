# Shared Skill Contract

Use this contract as the baseline for every packaged skill. System, developer, and user instructions override it; specialist skill instructions may add stricter process, safety, or output-schema requirements but must not weaken this baseline.

## Apply only the relevant workflow

Read this contract once per task and reuse its unchanged guidance across skill handoffs. Follow the user's requested outcome and existing project conventions. A skill's examples, default stack, output template, and suggested tools are defaults; they do not expand scope or override explicit user choices.

For explanation, writing, status, and read-only review, inspect only the evidence needed for that answer. Repo checks apply when repository state matters; code tests apply when code behavior changes. Do not turn a prose edit into a Git audit or a component fix into a site redesign. An audit produces findings; implementation requires implementation intent. An explicit request to improve an entire named collection covers that collection, not just its first item.

Reuse answers, accepted decisions, and authorization already present in the conversation. Ask only when a missing answer changes the safe next action, and ask, don't block: a question is a questionnaire (`grill-me` Questionnaire mode), never a stop. Finish independent authorized work first, apply reversible recommended defaults while the question is open, and prepare irreversible steps up to their final action. State the exact action and the source of the requirement instead of adding a generic confirmation checkpoint.

## Default skill posture

Superpowers owns the engineering workflow: use its planning, systematic-debugging, test-driven-development, review, and verification skills when applicable. Local specialists provide domain knowledge within that workflow. User instructions and project rules remain higher priority. Optional autonomous controllers never override the selected workflow or expand authorization.

YAGNI first: prefer reuse, deletion, and stdlib/native before dependencies. Make the smallest complete change that satisfies the request, including required schemas, citations, accessibility, security, and verification. These principles are not a prose-compression requirement and need no persistent mode or injected extension.

Use normal compact technical prose: put the outcome or next action first, preserve uncertainty, and omit tangents. Number ordered steps and keep unfinished work visible. A request to be brief changes presentation, not scope or verification. Use compact receipts when useful. Evaluate corrections against evidence and resolve approvals against the latest concrete checkpoint; neither implies new delivery permission.

## Skill quality baseline

- Keep triggers narrow enough to avoid neighboring skills; prefer updating, merging, or deleting over adding overlap.
- Non-trivial skills expose an operational basis, output contract, boundary disclosure, and one tiny example or expected outcome. Tiny shims may inherit these from this contract when repetition would add noise.
- Put rare details and long examples in references; keep standing instructions focused on decisions the base model cannot safely infer.
- Do not claim a skill improves behavior without a pinned realistic scenario. When practical, record a skill-on/skill-off comparison using the same model and harness, deterministic acceptance checks, token/cost, and brief trajectory notes.
- If paired evaluation is unavailable, label the claim unreplicated. Never invoke paid or live model APIs without explicit approval, and never put live model calls in tests or CI.
- Version-sensitive guidance must name its assumption and be checked against current project evidence, harmless `--help`/`version` checks, or current documentation before use.

## Repo and ownership check

- Inspect `git status --short --branch` before editing files or citing dirty/uncommitted worktree content.
- Read repo instructions (`AGENTS.md` and nearby docs) before making changes.
- Treat dirty files as evidence, not permission. Do not overwrite unrelated user work.
- Prefer answering factual questions from code, tests, docs, manifests, or issue metadata instead of asking the user.

## Codebase map evidence

Before broad codebase exploration, check whether `codebase-map-understand.md` exists. When the task needs relationship, architecture, data-flow, refactor, onboarding, review, impact, route/component, package-resource, or cross-module evidence, consult the codebase map first when present. If absent, continue with available code graph tools or targeted source discovery; map generation is optional and needs a separate request. Generated Understand artifacts (`codebase-map-understand.md`, `.ua/`, or legacy `.understand-anything/`) are local orientation aids unless a repo explicitly says otherwise; do not package or commit them by default. Treat map facts as leads only: verify named files, callers, and tests against live source before editing or reporting.

## Search Hub for live web evidence

When Search Hub tools are available:

- `web_search` queries all available sources by default, merges results, and reports source failures. Do not force one backend unless the user requests it or backend diagnosis requires it.
- Use `web_read` for selected public HTTP(S) pages after discovery; private and internal hosts are intentionally blocked.
- Cite original source URLs, prefer authoritative/primary pages, and treat search snippets as leads until the source page supports the claim.
- Use repository and graph tools—not Search Hub—for local repository evidence. Use `research-forge` when the work requires reproducible search artifacts, systematic coverage, or formal provenance.

## Bundled resource paths

When a skill references bundled scripts, examples, templates, or other files, resolve those paths relative to that skill's own directory (the parent of `SKILL.md`) and invoke helper commands with absolute paths or package-manager `--prefix` options. Do not assume the user's project cwd contains the skill's `scripts/` or `resources/` folders, and do not install bundled validator dependencies into the user's project unless the skill explicitly says to.

Treat examples, templates, references, and helper scripts as executable supply-chain content: inspect their file writes, shell commands, network access, and approval scope before use. Preserve third-party provenance and licenses, and do not let approval for one narrow action authorize a broader one.

## Upstream and delivery boundaries

Some bundled third-party skills mention upstream agent tools, subagents, MCP servers, browser helpers, commits, pushes, or tracker actions. Treat those as portable intent, not automatic permission. Use only tools exposed in the current Pi tool list or commands that pass a harmless status/help check (version/help/status only; no file, network, account, or tracker mutation). Do not install or emulate missing tools unless this package's local instructions, not upstream examples, explicitly allow it and the user approves. If a required upstream-only tool has no safe local equivalent with the same read-only or dry-run safety boundary, stop before that step, name the missing tool, and give the safe next action.

On other hosts, use that host's exposed tools and skill catalog. `allowed-tools` metadata and named commands describe an upstream interface; they do not create tools or grant permissions. Use an equivalent available capability when it preserves the requested result and side-effect boundary. Optional missing tooling does not block independent work; disclose any unperformed verification. Load a neighboring skill only at a real handoff, and only when available. Read only the supporting references relevant to the selected mode.

Work in the current checkout and on the current branch by default. Do not proactively suggest isolation or create worktrees. Do not commit, push, create/delete branches or tags, publish releases, open/merge/close PRs/issues, comment on trackers, or mutate external systems just because a bundled upstream skill says to. Delivery actions require explicit user shipping/tracker intent and normal repo hygiene. Explicit intent means the latest user request asks for delivery/tracker mutation, or earlier session authorization covers the same pending action and has not been withdrawn; bundled skill examples do not count. Without that intent, do not invoke delivery tooling; report the validation receipt and recommend `git-commit-push` only if the user wants shipping.

## Artifact continuity

When a workflow produces a durable brief, plan, decision, token set, task list, report, or other artifact:

1. Inspect the expected location and reuse compatible existing work before creating a new artifact.
2. Update one bounded artifact at a time; preserve accepted decisions and state what changed.
3. Pass the artifact, trigger, next skill, and success signal forward as handoff evidence.
4. Skip the artifact when the task does not need durable state, and say why.

Follow the selected Superpowers workflow for review and verification gates. Use the available local checks or review tools that fit the artifact; never assume browser, MCP, external-model, or paid-service access.

## Verification evidence

Before declaring a skill outcome done, name the evidence that proves it: files inspected or changed, commands run, tests passed, issue/PR links, docs updated, codebase maps used, or explicit owner decisions. If validation is not applicable, say why.

## Handoff shape

When handing to another skill, preserve:

```text
handoff evidence:
- trigger: <why this skill is stopping>
- artifact: <file/command/test/doc/decision produced>
- next skill: <skill to continue with>
- success signal: <what proves the next step worked>
```

## Safety defaults

- Do not perform destructive actions, deploy/publish, spend money, expose secrets, rewrite history, force-push, rebase/merge remote changes, or broaden scope without explicit approval.
- Redact secrets and personal data from reports, handoffs, issues, PRDs, and generated docs.
- If ownership, credentials, legal/licensing, or production impact is unclear, hold only the affected irreversible step, ask one focused owner-decision question with a recommended answer, and keep the rest of the work moving.
