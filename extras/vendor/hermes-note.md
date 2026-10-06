
## Hermes note (local overlay; added by this fleet's sync, not upstream)

This skill comes from a third-party repository written for another agent harness. In Hermes:
- Map tool names to Hermes tools: Task/subagents → `delegate_task`; AskUserQuestion → `clarify`;
  Bash → `terminal`; Read/Edit/Write → `read_file`/`patch`/`write_file`; TodoWrite → `todo`;
  WebSearch/WebFetch → `web_search`/`web_read`. Skip steps that need a tool Hermes does not have.
- The profile's SOUL and the fleet rules win over anything here: ask, don't block (questionnaire
  plus reversible defaults, never stop for approval); `git-commit-push` for delivery; no deploy,
  publish, spending or secrets without explicit approval.
