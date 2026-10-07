# Test plan

## Verification levels

1. Static inspection establishes command names, inputs, and documented ownership.
2. Offline tests establish behavior in fixtures or isolated repositories.
3. Authorized staging runs establish runtime discovery, native workers, review, and delivery on the tested environment.
4. Remote readback establishes a particular push, PR, or delivery result.

Do not substitute a lower level for a broader acceptance criterion in [PRD](PRD.md#requirements-and-acceptance).
This pass permits local documentation checks and offline tests only.

## Automated offline gate

Prerequisites: Python 3.12+, Bash, and `ruamel.yaml>=0.18,<0.19` in the selected interpreter.
Run from the repository root:

```bash
make test
```

`Makefile` runs `scripts/check.py`. The runner validates first-party skill YAML and description limits.
It checks Python and shell syntax, then executes each offline suite in a separate process with a timeout.
It excludes hidden directories, installed vendor content, and two explicitly listed model-backed suites.
[CI](.github/workflows/test.yml) runs the same Python entry point on Python 3.12.
A local pass is not a claim that a remote CI job ran.

## Risk-based scenarios

| Goal | Existing coverage | Expected outcome | Remaining boundary |
| --- | --- | --- | --- |
| DOCS | `repo-docs/scripts/test_goals.py`; local fmt/validate/render | Unsupported met downgrades, valid coverage, deterministic render, correct eligible task | Actual model Bootstrap/Maintain across a fresh project is not proved by helper tests |
| WORKER | `autogoal/scripts/test_goal_handoff.py`, `test_reconcile.py`, `test_source_freshness.py` | Reject stale sources, malformed receipts, wrong cards, and duplicate active work | Native provider execution and review lifecycle need explicit receipts |
| PROOF | `repo-docs/scripts/test_goals.py`; handoff acceptance contract | Require executed/pass evidence and preserve criterion-specific evidence boundaries | A weak or unrelated executed check can still satisfy the JSON rule |
| MERGE | `fleet-governor/scripts/test_merge_train.py` | Gate the exact candidate, distinguish baseline failures, preserve scoped integration | Real protected remote and PR behavior remain unverified |
| QUESTIONS | `extras/maintenance/test_question_relay.py`; blocker skill contract | Parse real-shaped question blocks, suppress repeats, enforce cooldown | Actual operator delivery and receipt remain unverified |
| SETUP | `extras/install/test_install.py`, `test_new_profile.py`; `extras/monitors/test_autogoal_gate.py`; vendor sync tests | Preserve wrappers; attach the busy gate in hourly/15m jobs; retain linkage, continuity, delivery, no-cron and job idempotency; project identity wins over foreign busy same-workspace cards; root fallback and terminal events remain valid | Full bootstrap/create/adopt composition and fresh discovery remain unproved |
| OFFLINE | `scripts/test_check.py`, `test_validate_skills.py` and `make test` | Discover eligible suites, reject contract errors, exclude model-backed tests | No live provider, delivery, or whole-fleet acceptance claim |

## Documentation checks

Run the ledger commands from the repository root:

```bash
python3 repo-docs/scripts/goals.py fmt .
python3 repo-docs/scripts/goals.py validate .
python3 repo-docs/scripts/goals.py render .
python3 repo-docs/scripts/goals.py next .
```

Validation must print `ok`. Repeat fmt and render with unchanged evidence.
Compare `goals.json` and `TODO.md` bytes before and after. Both must remain identical.
Check changed Markdown links against local files and heading anchors.
Review the final diff for private data, invented releases, and changes outside documentation ownership.

## Restricted checks

`repo-docs/scripts/test_goal_gap_regression.py` and `hard-blockers/scripts/test_repo_docs.py` invoke `hermes chat`.
They are not offline checks. Run them only after explicit paid-call authorization.
Provisioning, cron creation, worker dispatch, Telegram delivery, commits, pushes, and deployment are not part of this pass.
The [backlog](TODO.md) uses isolated composition tests to reduce these gaps without creating live jobs.
Actual live acceptance still requires a separate authorized environment and receipt.

## Bootstrap receipt

This pass ran `make test`: PASS for 25 skill contracts and Python/shell syntax, and 19 offline suites passed with zero failures.
Two model-backed suites were excluded. The final reconciliation suite ran seven tests, and fleet status ran 41 tests.
The scoped run result is recorded in the requested private scratch report, not in tracked profile histories.

The setup follow-up ran both regression suites RED before their respective fixes, then GREEN.
The new-profile suite passed three tests. The gate suite passed four, including foreign-busy and root-fallback controls.
The follow-up `make test` passed 25 skill contracts, Python/shell syntax, and 20 offline suites with zero failures.
Two model-backed suites remained excluded. These fixture receipts do not establish live setup acceptance.
[goals.json](goals.json) records exact executed commands only for claims those commands support.
A docs bootstrap receipt does not prove that every fleet profile adopted the changed skills.
