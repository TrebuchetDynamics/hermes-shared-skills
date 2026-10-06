---
name: upstream-reference-verification
description: "Use when verifying upstream clones and release freshness."
---

# Upstream Reference Verification

## Procedure

1. Treat an upstream-status question as a read-only audit, not authorization to synchronize. For this user's Wing work, preserve `hermes-desktop`, `hermes-agent`, and `hermes-conduit` as unmodified upstream software; do not introduce Wing-specific patches or builds. Updates must come from upstream rather than local implementation changes.
2. Locate named checkouts from project instructions and bounded filesystem discovery. Run `git -C <path> rev-parse --show-toplevel` first: Git can otherwise discover the enclosing product repository and report the wrong project's state. Report absent repositories as unverified, not clean or current. Never invent an upstream URL for an absent project.
3. Batch independent read-only checks per verified checkout:
   - `git -C <path> remote -v`
   - `git -C <path> status --short --branch`
   - `git -C <path> rev-parse HEAD`
   - `git -C <path> rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'`
   Confirm remote provenance against authoritative project information; a remote named `origin` alone proves nothing. Redact credentials if a remote URL contains them.
4. Check live freshness with `git -C <path> ls-remote <verified-remote> refs/heads/<target-branch>` and compare full commit IDs with the local head. Determine the target branch rather than assuming `main`. Run independent network checks concurrently with bounded timeouts. Prefer `ls-remote` for status-only requests because it does not update local tracking refs.
5. Classify provenance, worktree cleanliness, and freshness separately. A clean checkout can be outdated; an official remote can coexist with local deletions. Cached tracking-ref status is not proof of current remote freshness. Unequal live/local IDs establish a mismatch, not necessarily a behind relationship; do not claim ahead/behind counts without ancestry evidence.
6. Give a direct overall verdict, then one concise bullet per repository naming the failed dimension and short local/live IDs when relevant. Describe the search scope for missing projects and preserve unknowns if a network check fails. Do not save transient hashes, deleted-file lists, or current dirty state in skills or memory.
7. If synchronization is separately authorized, scope it to the named reference repositories; do not include the enclosing product checkout merely because the user says “all repos” while discussing references. Clone a newly supplied upstream URL into the requested project-root directory only after confirming that destination is absent. Inspect existing checkouts with `git status --short --branch`, `git diff --stat`, and `git diff --cached --stat` before updating. Use `git -C <path> pull --ff-only` for upstream updates: it permits a safe fast-forward while refusing divergence and conflicting local edits. Existing unrelated deletions may survive a successful pull; report them rather than calling the checkout unmodified. If an update conflicts with local work, stop that checkout and request an ownership/recovery decision; do not auto-stash, restore, reset, clean, or overwrite it. Treat cloning/updating reference source separately from installing dependencies or restarting an installed runtime.
8. Batch independent clone/pull operations with bounded timeouts, but keep their command results separate. Capture verbose fetch/diff output to a local artifact and return exit status plus a bounded summary instead of flooding the conversation with every upstream branch or changed file; large upstream repositories can produce enormous fetch output.
9. After updates, re-read each exact checkout's origin, current branch, full HEAD, worktree status, and live remote branch ID using `ls-remote`. Compare IDs programmatically. Report freshness and cleanliness separately, and name preserved dirty state as a remaining gap. Do not infer runtime installation, build success, or compatibility from a successful source update.

## Instruction persistence boundary

Separate acknowledgment of a standing rule from persistence of that rule. If an instruction-file write is denied or its approval expires, report that it was not saved and do not retry through another tool or path. A repeated statement of the rule is not evidence that the blocked write succeeded or that checkout updates are authorized.
