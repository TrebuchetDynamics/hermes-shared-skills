---
name: fleet-status
description: "Use when inspecting fleet health. Read-only status."
version: 0.1.4
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fleet, operations, status, read-only]
---

# Fleet Status

## When to Use

Use `/fleet-status` in the default fleet-governor profile for a concise read-only
dashboard. This is a local skill command, not a patched upstream CLI command.
Do not use it to repair profiles or implement project features.

Run `python <this-skill-directory>/scripts/status.py` through `terminal`.
The collector never launches Hermes CLI or imports its startup code: even nominal
read commands can migrate SQLite schemas or load `.env`. It reads allowlisted
simple scalar configuration directly; complex/ambiguous YAML is UNKNOWN. It reads
gateway-state timestamp/PID existence without claiming process identity or per-
profile transport health. Board paths follow the inspected native filesystem
layout. Exclude `kanban/boards/_archived`, the native archive container, from
live-board probes; archived databases inside it are not part of this dashboard.
The archived-card count covers archived rows in inspected live boards only. SQLite is opened `mode=ro&immutable=1` only when no nonempty WAL exists;
active WAL gives UNKNOWN rather than ignoring pending transactions or creating
shared-memory files. No databases are created or migrated. Supporting-file
symlinks/escapes and credential filenames are skipped and reported as incomplete.
It emits a redacted JSON snapshot to stdout only. Summarize its separate runtime,
work, blockers, automations, drift, security and operator-action dimensions.
Include observation time, coverage and UNKNOWN/STALE fields; do not replace them
with zero findings. Read-only collection never authorizes task transitions,
installs, restarts, retries, profile changes, credential access, deployments or
repository edits. Do not write receipts unless the user requests them.

Runtime availability is a shared-gateway observation, not profile/transport
health or successful execution. Work counts cover discovered readable boards,
not every external tracker or abandoned process. Archived cards are reported
separately: archival is neither delivered acceptance nor abandonment. A typed
needs_input/capability card moved to triage by the native block-loop detector stays
an operator blocker; ordinary new triage is not invented blocked work. Literal
triage remains in queued counts, not proof of dispatchability/productivity.
Blocker classification is a
heuristic over attributed latest run summaries, not verified current prerequisites.
Operator actions list only evidenced authorization/judgment/review gates;
unknown actions and technical remediation are not automatic human requests.
Do not infer operator approval from a prior task or a blocked status alone.

Shared drift covers the four configured shared skill families and their local
supporting files, not every custom/external skill. Read `skills.external_dirs`
only as a simple block list of absolute paths (plain, single-quoted or JSON-style
double-quoted, with optional comments); do not expand environment variables,
import Hermes/startup or load `.env`. Probe each family's known categorized and
flat paths in profile-local skills first, then explicitly configured external
roots. Local copies override external ones; multiple candidates in the same tier
are UNKNOWN rather than an arbitrary selection. Ambiguous/unsupported config,
unsafe symlinks and absent/unreadable external roots leave coverage UNKNOWN,
not proof of missing skills. Inventory hashes attest inspected files only;
runtime discovery, arbitrary layouts, create-dir and project skill tiers remain
unverified. Compare fleet-wide settings
against explicit expected defaults. Report model/provider/workspace/cadence as
profile-specific, not suspicious merely because they differ. An intentional-
difference label means preserved policy, not approval of any future change.

Sensitive-file checks inspect metadata only. No secrets or log contents are read.
Secret/log exposure, sandbox isolation, provider login, transport health,
production safety and billing are UNKNOWN unless separately inspected. Approval
bypass is a posture fact, not permission. Never label the entire fleet healthy.

Freshness: source observation older than 300 seconds is STALE; absent timestamps
are UNKNOWN. Automation last-run age is reported independently, with a default
86400-second stale threshold, configurable via `--automation-stale-seconds`.
A disabled job is not a failure. A successful picker is not downstream acceptance.

Regression: run `python <this-skill-directory>/scripts/test_status.py`.
For machine consumers use the JSON as emitted; do not synthesize extra totals.
Run a fresh collector for each request. Do not install this governor command in
project profiles or alter their skills/schedules to enable fleet administration.
