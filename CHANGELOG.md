# Changelog

## Unreleased

These entries describe notable changes present in the working tree. They do not establish a published release.

- Autogoal reconciliation checks receipt and readback shapes, exact card identity, and assignee ownership.
  It accepts an explicit nested current handoff without rewriting the journal.
- Fleet status inspects supported profile-local and configured external skill layouts.
  Ambiguous configuration, duplicate candidates, and unsafe paths remain UNKNOWN rather than falsely missing.
- Fleet status excludes the native retired-board archive container from live-board probes.
  An archive directory without its own database no longer makes readable live boards UNKNOWN.
  Archived-card totals still cover only rows in inspected live boards, not retired board databases.
- Recovery guidance distinguishes queued handoffs from worker execution, reconciles original cards after timeouts,
  and separates native goal-mode lifecycle constraints from generic CLI options.
- New project autogoal jobs attach the busy-card gate in both hourly and 15-minute setup branches.
  Existing jobs are not migrated. Offline fixtures cover job idempotency, linkage, and no-cron behavior.
- The autogoal gate uses invoking project `HERMES_HOME` before workspace matching.
  Foreign busy profiles sharing a workspace no longer control that invocation. Default/root fallback remains.
- A missing, not-yet-initialized Kanban database lets the picker run without the monitor creating state.
  Corrupt, dangling-linked or inaccessible existing boards still fail rather than being reported idle.
- The repository now has canonical product, design, verification, and local operations documents.
  A machine-readable goal ledger and bounded backlog expose remaining acceptance gaps.

## Release history boundary

No versioned release receipt was established in this bootstrap. Git commits are not treated as published releases.
Existing audit history remains in [the prior audit](docs/audits/2026-10-06-shared-skills.md).
Future release entries must use an actual tag or release receipt and verified scope.
