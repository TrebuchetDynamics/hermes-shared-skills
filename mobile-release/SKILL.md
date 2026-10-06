---
name: mobile-release
description: Use when releasing mobile apps. Check version and gates.
version: 0.1.0
author: "Profile owner, Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mobile, app-store, release, rollback]
---

# Mobile Release

Use this workflow for Android and iOS releases through app stores. It handles store-specific versioning, rollout, and verification; it complements rather than replaces general release-planning and monitoring rules. Follow repository instructions and higher-priority executor boundaries.

## When to Use

- Shipping a Flutter or native mobile app through Google Play or App Store Connect.
- Preparing a store hotfix, testing-track release, phased rollout, or production release.

Do not use this workflow for an ordinary code change that is not being prepared for a store release.

## Procedure

1. **Inspect the release contract.** Read the applicable `AGENTS.md` files, release runbook, version/build configuration, release scripts, CI workflow, and store checklist. Identify the official path, every version surface, signing/config requirements, publication stages, and approval boundaries before running commands.
2. **Freeze and scope the build source.** Record branch, HEAD, tracked edits, staged edits, and untracked paths. Reconcile every path with the user's release authorization. A Flutter build compiles the current working tree, including uncommitted app code, even when no files are staged. If a path appears or changes after approval, pause before building or publishing and ask whether it belongs in this release; do not assume an earlier “all current changes” approval covers later changes. Avoid blanket staging until the exact set is reviewed.
3. **Reconcile release identity.** Compare the repository marker, built artifact metadata, store changelog, local publication receipts, local and remote tags, and live store track state. A receipt proves a past publication, not current store state. A missing tag does not prove the version is unused. If any sources disagree, resolve the conflict with a live store readback or owner decision before selecting a version; never reuse a consumed build number.
4. **Choose the route and rollout explicitly.** Confirm the store, package, version/build, track, release status, and whether the repository's pipeline also publishes other channels. Prefer the official evidence-producing pipeline. If the owner explicitly waives CI or the cross-platform route and directs a Play-only release, treat that as route authorization rather than continuing to present the waived provider as a blocker; disclose the direct path's reduced provenance and test coverage. Never infer permission to bypass gates from missing credentials alone. Read back protected deployment variables only when using that pipeline; YAML defaults or local environment values do not prove the pipeline will use the requested track/status.
5. **Validate before publication.** Run formatter, analyzer, and focused regression tests locally, then let the official prepare/CI pipeline run its full suite and platform/device gates unless the owner explicitly chose a narrower route. On an explicitly approved direct Play route, run the available local gates and mark CI/full-suite coverage as unverified; a direct upload is not evidence those gates passed. A timeout or partial run is unknown, not a pass. When no canonical check covers a release-metadata invariant, use one temporary verifier in the authorized scratch directory (prefix `hermes-verify-`), assert the exact version/build, changelog, store-note, and dry-run selection, and remove it in `finally`. Report that result as an *ad-hoc check*, never as a green test suite.
6. **Require a recovery gate.** Before production publication, name a measurable health signal, numeric threshold, observation window, authorized owner, and exact recovery action. A repeated request to deploy or a choice of `completed` does not itself waive this separate gate; ask one concise clarification for the missing recovery details and do not commit the production edit until they are supplied. For Google Play `completed` releases, do not promise an in-place downgrade; a correction generally needs a new, higher-version hotfix. If the repository offers only full completion or draft, do not describe it as a percentage-staged rollout.
7. **Prepare, dispatch, verify.** Keep metadata preparation, remote commit, CI dispatch, approval, upload, and live-store publication as distinct states. Dispatch only through the authorized official mechanism and only after required gates pass. Read back package/version/build/track/status from the live store before claiming it is currently live. A current upload receipt supports an upload acknowledgement at its timestamp, not continuing live status.
8. **Report evidence precisely.** Separate local preparation, commits/pushes, CI results, upload acknowledgement, and live track state. Name commands actually run. Do not infer a successful upload from a dry run, local AAB, historical receipt, or a commit.

## Pitfalls

- A builder's next local build number can differ from the release workflow's prepared version; inspect both before deciding which is authoritative.
- A cached-tag dry run may not include remote tags. Treat it as a preview, not a live version check.
- Project-level protected track/status variables can persist and affect later releases. Do not alter them without authorization and a plan to read back or restore their prior values.
- Authentication failures leave remote state unknown; do not silently substitute an unguarded uploader. If the owner explicitly chooses Play-only instead of the unavailable or unwanted pipeline, use that route only after disclosing its reduced gates and satisfying the independent release gates.
- A full store release can differ materially from a Play-only upload because a repository release pipeline may also publish web or desktop artifacts.
- Direct Flutter builds include app-code changes in the working tree, whether staged or not; freeze and verify the exact build source before signing.

## Verification

A release is verified only when the intended source commit passed its required gates and the store's live version/build, track, and status match the authorized target. Keep any ad-hoc metadata probe explicitly separate from test-suite and CI results.

For the Google Play version-reconciliation and Flutter Fractal Forge pipeline details, see [Google Play release workflow](references/google-play-release.md).
