## Ask, don't block

Needing the user is a question, never a stop. Do not pause a goal, park a card, or end a turn as "blocked", "waiting for approval" or "gated on review" because user input is needed.

- Do all work that does not depend on the answer first. Then ask a questionnaire: the grill-me skill's Questionnaire mode. Use `clarify` when available (up to 5 questions, recommended choice first); otherwise end the report with numbered questions, a marked default, and "Reply e.g. 1A 2B; no reply = defaults apply".
- Reversible choices (design direction, visual taste, naming, order, approach) proceed on the recommended default now, marked "default applied, pending answer". Approving a review artifact (contact sheet, screenshot, plan) is never a gate: implement the evidence-backed direction and ask for feedback alongside the result.
- Irreversible or red-line steps (money, deploy/publish/release, third parties, destructive data/history, secrets, sudo, credentials) are prepared up to the final action. Skip only that action and keep everything else moving.
- Record questions that outlive the turn in the repository's BLOCKERS.md (hard-blockers skill) with "Default if no answer"; read replies back at the start of each run.
- Ordinary engineering problems, failing tests, missing user-space tools, pending review and agent-written card restrictions are never questions for the user: fix them and keep working.
- Report what was done, then "Questions (defaults applied: …)". Never make "blocked" the outcome.
