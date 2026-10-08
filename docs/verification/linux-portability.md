# Linux portability candidate verification

## Curated staged-source review

Independent review isolated the portability and fixture-pipeline changes from
pre-existing policy, mobile, graphify and archive work. The complete index
snapshot passed `make test`: 25 skill contracts and Python/shell syntax,
27 offline suites passed, zero failed, two model-backed suites excluded.
The exact staged-source provisioning suite separately passed all 11 tests.
Ledger validation printed `ok`. Private gate receipts bind the tested snapshot
to the index tree and every checked-out blob; raw machine receipts are not shipped.

The curated tree keeps the original `autogoal/SKILL.md` and worker policy. Only
the CLI timeout change and standalone check-receipt documentation are included
from the co-touched handoff files. The broader implementer results below include
unrelated local suites and are not the curated commit's suite count.

No blocking correctness issue was found in the scoped independent review.
A reference to uncommitted machine receipts was replaced with this portable
summary. `SETUP-4` and `SETUP-OPTIONS` are closed only for their isolated fixture
acceptance; native WORKER lifecycle and audio acceptance remain open.

## Prior implementer results

The final saved candidate passed `python scripts/check.py`: 26 skill contracts
and Python/shell syntax, 32 offline suites passed, zero failed, two model-backed
suites excluded. The frozen copy and selected Python environment were unchanged
before and after this gate. Command wall time: 19.798 seconds.

Focused checks passed:

- `python extras/install/test_provisioning.py -v`: 11 tests; explicit relocation,
  profile isolation, options, adoption, idempotency and negative controls.
- `python extras/install/test_local_stt.py -v`: four tests; readiness and the fake
  local audio boundary, not speech recognition.
- `python autogoal/scripts/test_check_receipt.py -v`: five tests; input/runtime
  reuse, failed checks, diagnostics, timeout and descendant cleanup.
- `python autogoal/scripts/test_pipeline.py -v`: three tests; real picker and
  handoff logic, fixture worker/check/review acknowledgement, duplicates, stale
  sources and timeout recovery.
- `python autogoal/scripts/test_cli_bounds.py -v`: one test, including nonzero
  exit and timeout subcases; no automatic mutation retries.
- `python extras/install/smoke_discovery.py --agent-dir <installed-Hermes-source>`:
  real CLI listing and fresh installed resolver content loads from canonical
  shared directories in an isolated temporary home; exit 0.
- `python extras/install/smoke_stt.py`: real isolated CLI configuration/readback,
  repeated apply, retained unrelated settings, disable and cleanup; exit 0.

All check subprocesses had an outer limit of at most 300 seconds. Final runs
used the private scratch directory and disabled Python bytecode output. Detailed
logs, pre/post hashes, dependency identity and timings remain in private scratch,
not in the commit. No packages, models, live profiles, jobs or cloud services were
changed. No commit, push or integration was performed by the implementer.

## RED/GREEN and review findings

Observed failing tests preceded the fixes for unsupported explicit relocation,
missing STT readiness, unbounded native CLI calls, missing check receipts,
receipt CLI argument parsing, surviving timeout descendants, missing failure
diagnostics, unrelated-root deduplication, profile path traversal and symlinked
out-of-profile configuration writes. Each was followed by the corresponding
passing focused check. Composition tests characterize existing option behavior;
they are not presented as new behavior with a fabricated RED phase.

The initial full gate failed on an unchanged, pre-existing oversized
`autogoal/SKILL.md`. Two prose-only reductions preserve the task budget, native
worker requirement and authorization boundary. A focused rerun first showed the
body was still over its existing limit; a further wording reduction fixed it.
No test limit or assertion was weakened.

A subsequent passing gate observed unrelated mobile-release edits during its
run. Those edits were preserved. The final gate therefore ran on an exact saved
copy, with copy-time and pre/post fingerprints, instead of claiming the mutable
checkout was frozen. Receipt reuse is scoped to matching relevant inputs.

Implementer review covered preservation boundaries, refusal tests, receipt
provenance, no-download audio behavior, CLI argument parsing, timeout cleanup and
changed English prose. Parent independent review and curated-index verification
remain separate. Full ASD-STE100 dictionary compliance was not assessed.

## Acceptance boundaries

- Actual audio transcription: **NOT_RUN**. The installed dependency probe found
  no `faster_whisper` and no default cached model root. Readiness is not audio
  acceptance. `SETUP-AUDIO` retains that optional check without authorizing a
  download or installation.
- Native worker/provider execution, native retry exhaustion and acknowledged
  native review: **NOT_RUN**. The dispatch setting is three attempts; the helper
  and receipt runner do not add blind retries. The composed review sink is a
  fixture, not proof of a native review lane.
- Reusable receipts require all relevant declared inputs. The helper cannot
  discover arbitrary dependency closure or independently authenticate a receipt.
- Review handoff is not approval. Integration remains explicit and unperformed.
- Supported scope is Linux with an existing installation. No clean-machine,
  distribution matrix, macOS, Windows, live scheduler, remote CI or fleet-wide
  certification is claimed.

The implementer supplied executable candidate evidence for `SETUP-4`,
`SETUP-OPTIONS` and the fixture part of `WORKER-1`. Independent curation closed
only the first two after review and the staged-source gate. Broader SETUP,
WORKER and PROOF goals remain open; fixture evidence does not mark them met.
