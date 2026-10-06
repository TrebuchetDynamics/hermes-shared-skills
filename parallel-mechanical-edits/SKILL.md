---
name: parallel-mechanical-edits
description: "Fan out a mechanical change across files via subagents."
version: 1.0.0
author: SDRHF Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [subagents, delegation, refactor, verification, mechanical-edits]
---

# Parallel mechanical edits

Fixing the same thing in fifteen files — wire a constant in, rename a call, add a guard — is a fan-out job: recon → exact site list → disjoint file sets → one subagent per set → central verification. Use `delegate_task` with one task per file set.

## When to Use

Load this when a change is identical in kind across many files and partitions cleanly by file. Not for changes needing cross-file judgement, and not when a single edit would do.

## Procedure

1. **Recon completely before dispatching.** Produce the exact site list yourself: `file:line` plus the surrounding snippet for every edit. A subagent handed a vague goal invents its own scope.
2. **Partition by file, never by concern.** Two children must not share a file — concurrent edits to one file race and one silently overwrites the other.
3. **One task per file set**, with context assuming the child knows nothing of your session: absolute repo path, exact file paths, the exact `old → new` strings, the convention to follow, and the values that must not change.
4. **Forbid the test suite inside children.** Tell them explicitly: siblings are mid-edit, so a suite result is meaningless and a "passed" report is noise. The parent runs it once, at the end.
5. **Forbid git writes** in children (`commit`, `add`, any write command) unless the user asked for delivery.
6. **Verify centrally.** Child summaries are self-reports, not evidence. Read `git diff` for every file they touched, hunk by hunk, against your own site list; then run the suite and the typecheck once yourself.
7. **Residual sweep.** After everything, grep for each literal or pattern you replaced across the whole tree. Empty (doc comments excluded) is the only acceptable result.

## Pitfalls

- **Never build the work list from a truncated scan.** Output truncated by a print cap (`slice(0, n)`, a per-item print limit, a paged shell view) turns N real sites into the handful that happened to print, and that sample then gets reported as complete. Count the matches first, enumerate every one, and prefer an untruncated sweep over a "top few" print. Say "N sites found" only after counting them.
- **Dependent lanes cannot be dispatched concurrently.** If one lane's edit *imports a symbol another lane creates*, parallel children each see a half-built tree: any typecheck inside either fails spuriously, and a child may "helpfully" repair the breakage by inventing the missing symbol somewhere you did not intend. Either create the shared symbol in the parent before dispatching, or sequence the dependent lane after its producer. If you do dispatch them together, tell each child in advance that a sibling is mid-edit and that a transient unresolved-import is expected — make the assigned edit correctly and do not work around it.
- **A child that edits outside its assigned files is a failure, not a bonus.** Constrain scope explicitly, then check `git status` for files you never assigned.
- **Whole-tree greps need path exclusions**, or your own generated artefacts (analysis output dirs, logs) flood the result and hide the real hits.
- **A value-matching check cannot confirm pairing** when the value is not unique. If a number is shared by several candidate constants (a real case: `20` was shared by seven), "the literal equals the declared value" proves nothing about *which* constant belongs at that site — decide the pairing by reading the consumer's intent and confirm it against the doc comment on the constant.
- **"Behaviour-preserving" is a claim to test, not assume.** When the edit changes the *form* of the output (literal → bound parameter, inline → helper call), it is only equivalent-if-nothing-breaks; report that half as unexercised until something exercises it.
- **Split the change report by risk**, not by file: say which files are provably inert and which changed shape and therefore need a real run.

## Output contract

Close with: the diff review, the suite/typecheck result, the residual sweep, and anything a child was told not to do. Name the checks you did not run.
