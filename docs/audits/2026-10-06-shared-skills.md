# Shared-skills audit — 2026-10-06

Baseline: `2a284827ec516df0181c801c174b10e6b3a69bd0` (initial working tree clean).
Scope: first-party skill contracts, offline regression coverage, installer/wrappers,
monitor gates, vendor pinning, and fleet status/question collectors. This is not an
exhaustive semantic review of every workflow or proof of live fleet behavior.

## Verified defects repaired

| Surface | Defect and repair | Regression evidence |
|---|---|---|
| Installer | Python source interpolation and runtime-path regex mishandled quotes/backslashes. Pass paths as arguments, parse the source-root literal through AST, and encode generated wrapper paths with Python representations. | `extras/test_install.py`: shell entry point and generated wrappers execute with quoted/backslash fixture paths. |
| Managed wrappers | Reinstallation retained stale paths after repository relocation. Refresh exact current/legacy generated bodies; preserve custom or customized scripts. | Installer tests cover relocation, legacy upgrade, custom preservation, idempotence, and byte-preserving dry runs. |
| Autogoal monitor | A default-only installation without `profiles/` raised an exception. Return the existing snapshot when the directory is absent. | `extras/monitors/test_autogoal_monitor.py`. |
| Documentation monitor | Committed docs were compared with working-tree path existence, creating or hiding drift during uncommitted source edits. Compare repository-local references with the committed tracked tree. | `extras/monitors/test_repo_docs_monitor.py`: uncommitted deletion/recreation leaves the snapshot unchanged; committed deletion produces drift. |
| Vendor sync | `--pin` fetched the existing pin rather than upstream HEAD. Fetch HEAD only when repinning; preserve ordinary pinning and dry-run manifest behavior. | `extras/vendor/test_sync_vendor.py`; fetch/install are mocked, no upstream update performed. |
| Fleet status | The CLI entry point selected the user-home ancestor instead of the Hermes-home ancestor. Malformed runtime/scheduler JSON could also crash collection. Correct the ancestor and report unsupported shapes as unknown. | Three added cases in `fleet-status/scripts/test_status.py`. |
| Fleet question collector | Duplicate-field diagnostics were not entry-prefixed, allowing one invalid record to suppress unrelated valid entries. Attribute defects to their exact entry. | Added Active/Resolved duplicate-field subcases in `fleet-blockers/scripts/test_collect.py`. |
| CI coverage/contracts | CI omitted fleet-status and helper suites; regex-only frontmatter validation accepted invalid structured metadata. Use `scripts/check.py` for all offline suites, real YAML contracts, and Python/shell syntax. | `scripts/test_check.py`, `scripts/test_validate_skills.py`; CI runs the same entry point. |

## Improvements

- Nine routing descriptions now fit the 60-character catalog budget: 2,063 characters
  reduced to 476 (1,587 removed), without changing skill names or workflow bodies.
- `scripts/validate_skills.py` checks YAML mappings, scalar descriptions, slug/directory
  agreement, platform lists, loader size limits, nonempty bodies, and duplicate YAML keys.
- Empty catalogs fail rather than passing vacuously. Hidden, vendored, and symlinked
  skill paths are excluded. First-party `extras/vendor/` tooling remains included.
- `scripts/check.py` runs suites in separate processes with 180-second timeouts.
  Two explicitly model-backed suites remain manual.
- `make test` and `make check` expose the offline check to command detection.
- README documents the dependency, command, exclusions, and model-test boundary.
- `codebase-audit-verification` now teaches checking runner coverage and structured
  metadata with the actual parser rather than accepting regex/green-suite heuristics.

## Independent review and corrections

Read-only independent review found two defects in the newly added checks. Both were
reproduced with failing tests and corrected:

1. `ast.parse` accepts context-invalid statements such as module-level `return`, `break`,
   and `await`. The syntax gate now uses `compile(..., 'exec')` without executing source.
2. Catalog discovery included hidden/symlinked directories despite the advertised
   exclusion. Validation and reported counts now share filtered catalog discovery.

The parent reviewed the combined installer, collector, monitor, and vendor changes
and ran all resulting offline suites. This does not claim independent review of every
helper change.

During pre-commit review, a further monitor regression was reproduced: lexical
committed-path membership falsely marked valid links through committed directory
symlinks as broken. The delivery fix resolves symlink components from HEAD rather
than the mutable working tree, with cycle/depth protection. Four monitor integration
tests cover directory/file symlinks, uncommitted retargeting, broken/cyclic links,
and backticked paths through root-level directory aliases (including aliases to `.`).

## Executed verification

- Initial offline suites and Python/shell parsing passed before repairs; their green
  result did not cover the newly reproduced defects.
- `python scripts/check.py`: 25 first-party skill contracts, Python/shell syntax, and
  all 16 offline suites passed.
- `hermes verify /home/xel/.hermes/shared-skills --phase test --skip-start --json`:
  detected and executed `make test` and `make check`, both exit 0.
- Disposable Python 3.12.14 environment with only `ruamel.yaml` installed, temporary
  HOME/HERMES_HOME, and no Hermes executable on PATH: `scripts/check.py` passed
  all 16 suites / 126 tests, exit 0. The environment was removed afterwards.
- Targeted regressions reproduced the syntax/catalog failures before their fixes.
- `git diff --check`: passed.

An initial attempt to create the disposable environment through the local `python`
launcher failed because the launcher was copied instead of its underlying interpreter.
The subsequent `uv venv --python <real-interpreter>` setup worked. That setup failure
was not a repository test failure and is not counted as a pass.

## Verification limits and side effects

- No real-model regressions, live fleet repairs, actual upstream vendor fetches, or
  remote GitHub Actions runs were performed.
- Profiles, cron jobs, credentials, approval settings, and SOUL snippets were not changed.
- Installer tests used temporary profile files and a fake Hermes launcher; the clean
  environment check proves offline portability, not a live installer rollout.
- Vendored upstream skill content was not modified or exhaustively audited.
- At audit completion, changes remained local and uncommitted; no commit, push,
  release, or deployment occurred during the audit. Subsequent delivery is recorded
  in Git history rather than asserted by this pre-delivery report.
- These conclusions apply to this working tree and must be rechecked after relevant changes.
