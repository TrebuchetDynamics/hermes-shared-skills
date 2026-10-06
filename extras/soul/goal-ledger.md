## Goal ledger

If the repository has a `goals.json`, every card that advances a goal (follow-up cards
included) finishes with `python ~/.hermes/shared-skills/repo-docs/scripts/goals.py`:
`task <repo> <TASK> done`, then `evidence <repo> <GOAL> --kind executed --ref "<exact
command>" --result pass|fail` for each check you actually ran, then `render <repo>`. A goal
is met only with an executed, passing check. Never hand-edit goals.json.
