# Product requirements

## Purpose and authority

This package gives Hermes profiles shared skills and setup tools for a goal-led fleet.
Operators need current project documentation, bounded workers, review handoffs, and verified Git integration.
The accepted scope below comes from [README](README.md#design-rules) and the existing skill contracts.
It does not introduce a new service or approve a release.

## Users

- Project profiles maintain one repository and implement bounded goal tasks.
- The default profile coordinates fleet health, questions, and the daily merge train.
- Operators answer irreversible decisions and inspect evidence without reading private session histories into this repository.

## Requirements and acceptance

| ID | Requirement | Observable acceptance | Current evidence boundary |
| --- | --- | --- | --- |
| DOCS | Keep core docs current and turn non-met goals into tasks. | Bootstrap creates applicable owners. Maintenance preserves an unchanged ledger byte-for-byte. Every non-met goal has a bounded task. | This repository has a local bootstrap receipt. Real-model regressions exist but were not run in this pass. |
| WORKER | Select one goal-linked slice and hand it to a bounded native worker. | The selected task, exact card, assignee, source snapshot, and 50-turn budget agree. Retries do not duplicate active work. The worker implements, tests, and hands off to review. | Offline contract and reconciliation tests are not proof of provider execution or review approval. |
| PROOF | Mark a goal met only after an executed passing check. | Unsupported met claims become unverified. Completion evidence maps to the actual acceptance criteria and source. | The ledger enforces presence of executed/pass evidence. It cannot determine whether that check proves the whole goal. |
| MERGE | Keep main current through gated integration. | Finished card branches reach the candidate tree. New failures block landing. Baseline failures remain distinct. Required PR paths and submodule ordering are respected. | Isolated Git regressions do not prove live remote landing or branch protection. |
| QUESTIONS | Ask the operator and continue independent work. | Owner questions include reversible defaults. Technical failures do not become invented owner decisions. Repeated questions are deduplicated. | Relay fixtures cover parsing and cooldown. Actual delivery and owner receipt remain unverified. |
| SETUP | Wire shared skills into default and project profiles. | Reinstallation preserves custom files. Generated wrappers resolve the canonical checkout. Fresh discovery sees the skills. Job setup and optional integrations match documented behavior. | Helper fixtures pass. Fresh-machine provisioning, live discovery, and delivery need separate receipts. |
| OFFLINE | Provide one reliable offline verification entry point. | The runner validates first-party skill contracts and syntax, isolates suites with timeouts, and excludes model-backed suites. | `make test` is the local acceptance check. See the test plan for scope. |

## Constraints and non-goals

- Keep profiles, credentials, sessions, and private operator histories outside this tracked package.
- Preserve other workers' dirty files and claims. Do not rewrite their history to distribute skills.
- A skill catalog on disk is not evidence of adoption by an existing session.
- OMH is optional and separately installed. Bootstrap does not install it.
- This package does not own Hermes' HTTP API, provider runtime, Telegram transport, or upstream plugins.
- This documentation pass does not authorize paid model calls, live setup, jobs, releases, commits, or pushes.
- Unit tests establish their tested behavior only. They do not close the broad fleet requirements.

## Priorities and goal status

The README workflow order drives the backlog: documentation, worker handoff, evidence, integration, questions, then setup.
[goals.json](goals.json) owns status and evidence. [TODO](TODO.md) owns bounded task details.
[The test plan](test-plan.md) defines proof methods rather than product requirements.
There are no new owner-only decisions in this bootstrap. Future irreversible choices use [BLOCKERS](BLOCKERS.md).
