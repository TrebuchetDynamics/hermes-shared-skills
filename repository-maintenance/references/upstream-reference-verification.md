<!-- Consolidated reference; original metadata is provenance, not a command.
name: upstream-reference-verification
description: "Use when verifying upstream clones and release freshness."
-->

## Mode boundary

Read-only verification uses Procedure steps 1–6 only. No fetch, pull, reset, clean, clone, switch, build, dependency installation or runtime restart is implied. Steps 7–9 are synchronization guidance and apply only under a separately authorized Synchronization mode. Vendored verification and instruction-persistence rules apply in either mode.

# Upstream Reference Verification

## Procedure

1. Treat an upstream-status question as a read-only audit, not authorization to synchronize. Establish the official product repository and, for a monorepo, its application subtree before using any existing clone as a reference. For a monorepo reference, resolve the official application subtree from that project's current authoritative instructions; a similarly named separate checkout is not product authority. Preserve reference checkouts as unmodified upstream software; do not introduce port-specific patches or builds. Updates must come from upstream rather than local implementation changes.
2. Locate named checkouts from project instructions and bounded filesystem discovery. Run `git -C <path> rev-parse --show-toplevel` first: Git can otherwise discover the enclosing product repository and report the wrong project's state. Report absent repositories as unverified, not clean or current. Never invent an upstream URL for an absent project.
3. Batch independent read-only checks per verified checkout:
   - `git -C <path> remote -v`
   - `git -C <path> status --short --branch`
   - `git -C <path> rev-parse HEAD`
   - `git -C <path> rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'`
   Confirm remote provenance against the official project's own README, release/docs links and repository organization; a remote named `origin`, a matching app name or stale project instructions prove nothing. For a monorepo, run `git -C <root> ls-tree HEAD <app-subtree>` and inspect that subtree's README and guides before accepting it as the product reference. Record repository revision and subtree separately. Redact credentials if a remote URL contains them.
4. Check live freshness with `git -C <path> ls-remote <verified-remote> refs/heads/<target-branch>` and compare full commit IDs with the local head. Determine the target branch rather than assuming `main`. Run independent network checks concurrently with bounded timeouts. Prefer `ls-remote` for status-only requests because it does not update local tracking refs.
5. Classify provenance, worktree cleanliness, and freshness separately. A clean checkout can be outdated; an official remote can coexist with local deletions. Cached tracking-ref status is not proof of current remote freshness. Unequal live/local IDs establish a mismatch, not necessarily a behind relationship; do not claim ahead/behind counts without ancestry evidence.
6. Give a direct overall verdict, then one concise bullet per repository naming the failed dimension and short local/live IDs when relevant. Describe the search scope for missing projects and preserve unknowns if a network check fails. Do not save transient hashes, deleted-file lists, or current dirty state in skills or memory.
7. If synchronization is separately authorized, scope it to the named reference repositories; do not include the enclosing product checkout merely because the user says “all repos” while discussing references. Clone a newly supplied upstream URL into the requested project-root directory only after confirming that destination is absent. Inspect existing checkouts with `git status --short --branch`, `git diff --stat`, and `git diff --cached --stat` before updating. Use `git -C <path> pull --ff-only` for upstream updates: it permits a safe fast-forward while refusing divergence and conflicting local edits. Existing unrelated deletions may survive a successful pull; report them rather than calling the checkout unmodified. If an update conflicts with local work, stop that checkout and request an ownership/recovery decision; do not auto-stash, restore, reset, clean, or overwrite it. Treat cloning/updating reference source separately from installing dependencies or restarting an installed runtime.
8. Batch independent clone/pull operations with bounded timeouts, but keep their command results separate. Capture verbose fetch/diff output to a local artifact and return exit status plus a bounded summary instead of flooding the conversation with every upstream branch or changed file; large upstream repositories can produce enormous fetch output.
9. After updates, re-read each exact checkout's origin, current branch, full HEAD, worktree status, and live remote branch ID using `ls-remote`. Compare IDs programmatically. Report freshness and cleanliness separately, and name preserved dirty state as a remaining gap. Do not infer runtime installation, build success, or compatibility from a successful source update.

## Vendored skill verification

When an authorized integration vendors upstream skills, inventory every candidate against existing owners before selecting additions. Pin the inspected source and preserve its license; keep native adaptations reproducible rather than appending contradictory harness instructions. Keep frontmatter-bearing adaptation templates in a non-discoverable format such as `.md.in`: Hermes can discover standalone `.md` files and make the installed name ambiguous. Verify in a fresh native Hermes bootstrap that bare names, slash aliases and invocation payloads resolve to the intended canonical paths, not a higher-precedence local copy. Installation, command construction, live menu publication and actual task execution are separate claims. Keep machine-specific receipts private and do not restart healthy workers to propagate wording.

## Instruction persistence boundary

Separate acknowledgment of a standing rule from persistence of that rule. If an instruction-file write is denied or its approval expires, report that it was not saved and do not retry through another tool or path. A repeated statement of the rule is not evidence that the blocked write succeeded or that checkout updates are authorized.
