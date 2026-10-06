# Source-graph-assisted behavioral audits

Use when the request combines a named repository analysis engine with finding correctness, causality, accounting or integrity issues. Deterministic extraction is an evidence map, not a bug detector or behavior certificate.

## Scope and extraction

1. Record the current source commit and dirty paths; read module instructions, manifest and binding contracts before testing. Recheck old findings against this source because retained expertise may describe a different revision.
2. Export allowed tracked source into a fresh non-Git snapshot with `git archive`. For a module request, scan the exported module root rather than scanning the whole repository and filtering the graph afterward; this preserves meaningful module-relative imports and makes coverage explicit.
3. Inspect the allowed-file list before reading contents. Include defining manifests, schemas and fixture contracts; exclude actual datasets, raw evidence, credentials, caches and run/checkpoint artifacts. Distinguish a schema describing an artifact from the artifact itself.
4. Run Understand-Anything's native scanner, import resolver and structural extractor as described in `knowledge-graph-extraction.md`. Retain their real outputs and validate coverage, ranges and endpoints. Do not present generic file-name summaries as semantic review.

## Select investigation seams

Trace actual dependency edges through input validation, transformations, accounting, serialization and output consumers. Partition parallel reviewers by disjoint behavioral responsibility, not arbitrary file count, so one reviewer owns each shared seam. Useful scopes for offline research include:

- Model, evaluator, normalizer and checkpoint integrity.
- Causal admission, deadlines, continuity and journal-backed release.
- Feature construction, ingestion/assembly, execution and fee accounting.

Require every reviewer to return executable probes, actual commands/results, source ranges, positive controls, severity/impact and explicit limits. Do not let a source-only claim become reproduced merely because multiple reviewers repeat it.

## Execute safe counterexamples

1. Read test bodies and fixtures before choosing tests. Select explicit files or test names instead of collecting the entire research suite, because test collection or helpers may launch training, access corpora or make network calls.
2. Run tests with an existing suitable interpreter against the snapshot through `PYTHONPATH`; write probes, pytest cache and temporary journals only into the audit workspace. Do not alter product source to obtain a reproduction.
3. Construct subprocess environments from an allowlist rather than inheriting credentials. Supply only required runtime values such as `PATH`, `HOME`, `TMPDIR`, locale, snapshot `PYTHONPATH` and `PYTHONDONTWRITEBYTECODE=1`. For lightweight CPU probes, use `CUDA_VISIBLE_DEVICES=''`, `OMP_NUM_THREADS=1` and `MKL_NUM_THREADS=1`; these are resource controls, not proof that a test cannot train.
4. Prefer tiny hand-computable synthetic inputs and stub policies over trained checkpoints or historical datasets. An initialized model may suffice for serialization checks; do not execute optimizer updates merely to test loading or integrity.
5. Pair each adverse input with a valid control reaching the same boundary. Assert the violated invariant directly: actual realized reward versus reported total, post-deadline input versus admission, altered normalizer versus loader acceptance, or declared execution size versus binding contract.
6. Keep evidence classes distinct. A contract constant mismatch can be verified by source/config comparison without proving an executed trade used it. A loader accepting modified metadata is a runtime reproduction but not proof that historical results were corrupted. An absent integration seam is source-only until the operational path is inspected.
7. Preserve exit codes, stdout/stderr, probe source and source hashes. Name the expected failure signal; a successful harness exit may mean it detected the defective behavior, not that the product passed. Use discriminating assertions rather than console-only observations.

## Verification and reporting

Read delegated artifacts and spot-check consequential source claims before aggregation. Programmatically deduplicate findings by root cause and reconcile counts. For each finding report severity, status, affected source, expected versus observed behavior, command/receipt, impact and reproduction limits. Separate passed controls, skipped gates and untested scope.

Keep graph schema/search checks separate from product regression tests, runtime verification and scientific clearance. End a background handoff with a brief pending status; do not call a scan-complete progress message the finished issue report. When findings return, deliver the issues and receipts, not a replay of indexing steps.

Do not repair product code as part of a find-issues-only request. Preserve unrelated changes and leave implementation, release, historical-impact assessment and production verification as separately scoped work.
