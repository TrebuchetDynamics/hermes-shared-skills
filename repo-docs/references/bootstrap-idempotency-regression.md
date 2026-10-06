# Bootstrap and second-run behavioral regression

Use this check after changing default Bootstrap/Maintain policy. Skill text,
installation hashes and command routing checks are not behavioral evidence.

1. Create an isolated scratch fixture containing README.md, pubspec.yaml,
   lib/main.dart and test/counter_test.dart. Supply explicit accepted product
   intent and accurately labeled synthetic release evidence in the README.
   Include one demonstrably stale README test path. Use a local-only Flutter
   counter with initialization, increment and reset; no owned HTTP server and
   no architectural approval history. Do not infer intent or a release from a
   version string alone.
2. Bound documentation writes to the fixture. Preserve source, test and manifest;
   prohibit installs, Flutter execution, production operations, network probes,
   profile/schedule edits, agent-instruction edits, commits and goal dispatch.
   The reduced fixture has no platform runners; docs must disclose that limit.
3. Snapshot all input paths and SHA-256 bytes. Check live CLI help, then invoke
   the actual bare `/repo-docs` using `hermes chat --in <fixture> -q /repo-docs
   --oneshot -Q --max-turns <bounded-budget> --run-budget <seconds>` through
   `terminal`. Do not replace it with a bespoke Markdown generator or an extra
   prompt that specifies all expected output files. Preserve stdout, stderr,
   session ID, command, model/profile context and exit code.
4. Read back the created documents independently. Verify supported README repair;
   substantive PRD/spec/test-plan/local runbook/changelog content grounded in the
   supplied intent/source/tests/release record; navigation and TODO handoff;
   no ADR directory or OpenAPI file; unchanged source/test/manifest fingerprints.
   Check current versus proposed/unexecuted claims. A successful agent summary
   alone cannot satisfy these assertions.
5. Snapshot the complete output tree, then run the same bare command again in a
   fresh session with the same fixture. Require identical path sets and identical
   byte hashes, including TODO.md. Read its result and verify no claimed repair
   or invented new task. Mtimes and a no-op summary alone are insufficient.
6. Preserve fixture, snapshots, transcripts and the assertion receipt outside
   automatically pruned scratch. Distinguish actual command execution from
   product test execution. One successful fixture observation does not establish
   universal adherence, all profile/provider behavior or repeated-run reliability.

If the second run changes a file, inspect the diff. A genuine first-run defect
means bootstrap was incomplete; style churn or date bumps mean idempotency failed.
Fix supported policy issues and repeat from a fresh fixture. Do not reset hashes
or relabel a rewrite as a no-op. Add separate fixtures for equivalent canonical
paths, missing product/release evidence and owned/generated API contracts when
those behaviors need proof; the local Flutter fixture cannot establish them.

## Goal-gap fixture (v0.4)

`scripts/test_goal_gap_regression.py [fixture]` automates steps 3–5 on a fresh
fixture. The fixture's README lists owner-approved GOAL-1..GOAL-4, where GOAL-4
(decrement, floor at 0) is not implemented. Besides the checks above, it asserts:
- the six baseline docs are built;
- TODO.md has a `Goal coverage` table;
- GOAL-4 is marked unmet, partial or unverified and has an open task keyed to it;
- the second pass is byte-exact (no duplicate goal tasks).

It refuses a non-fresh fixture. Rebuild the fixture before every run.
