# <YYYY-MM-DD> — <subject> audit

Read-only audit of <scope: the live service / the repository / the subsystem>.
No code, config, or live-service change was made by this pass.

Method: <the exact commands and sources you read>. Name what you did **not**
run, so coverage is bounded.

## The observation

<The measurement that raised the question, with the command that produced it and
the window it covers. A table beats prose. Show the totals reconciling, because a
reconciling total is what makes a delta interpretable.>

## What it is NOT (retraction)

<State the first reading plainly, then why it is wrong. Quote the counter-evidence:
the comment, guard, or prune in source that names the same divergence; the current
state that contradicts the inference; the timings that show the mechanism already
ran. Name where the numbers in the first reading actually came from — usually a
window in which the condition still held. A retraction section is the most valuable
part of the record: it stops the next reader re-deriving the same wrong conclusion.>

## The defect this exposed

<The real, surviving defect. Find the function that writes the field or decides the
behaviour and count its write sites. Give the file + symbol, the mechanism, and the
operator-visible consequence. If nothing survives, say so here.>

## Other findings

<Numbered. Mark each as validated by a command, or as a hypothesis still needing
one. Include the things that are correct-but-surprising: a re-catch loop that a
ranking metric correctly discounts belongs here, not in a fix list.>

## P0 plan

<One item per fix. Each carries: the objective, the exact files, its scope
exclusions (pinned parameters, code areas that must not be touched because they sit
against a size ceiling, anything needing separate authorization), the acceptance
check, and the dependency — a fix whose live confirmation needs a restart is
dependency-ready for the change and gated for the verification. Rank so the one
that is ready without a maintenance window is obvious.>

## Redeploy

<Per component, the exact command, and whether it restarts anything live. Distinguish
components whose deploy is safe from those that interrupt a running service, and say
which one needs an operator-selected window.>

## Audit trail

<Which ledger entries were retracted **in place** (original prose preserved, dated
note added) versus corrected, and where the original framing still lives. A ledger
left asserting the retracted reading is a false statement you introduced.>
