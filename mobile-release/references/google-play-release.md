# Google Play release workflow

Use this reference after inspecting the app repository's current release instructions. The Flutter Fractal Forge commands below are project-specific examples; do not assume another repository has the same scripts or version marker.

## Reconcile the version

Compare all of these before choosing a build number:

- `fdroid/version.properties` (`versionName` and `versionCode`) as the repository's prepared release identity.
- `scripts/build-play-console.sh --print-version` as the standalone builder's local next-version calculation.
- `play-console-upload/LATEST_BUILD_INFO.txt` and AAB manifest values when a local artifact exists.
- Local Play publication receipts, including package, version code, track, status, and timestamp.
- Local and remote release tags, plus the live Play Console track state.

A local receipt for `production`/`completed` is historical evidence of a submitted release. Confirm current live state before selecting another version. If the release launcher still selects a code already present in a receipt or store track, stop and reconcile tags, markers, and store state; do not publish the same code again. A cached-tag dry run is not a substitute for fetching remote tags.

## Flutter Fractal Forge pipeline

The repository runbook defines this flow:

1. `./release.sh --dry-run` is read-only and reports a plan from cached tags; it does not fetch tags, build, commit, push, or publish.
2. `./release.sh --prepare` prepares the next patch, pushes the prepared branch to both remotes, and dispatches full platform/device/evidence verification without publication.
3. After the prepare pipeline passes, `./release.sh --publish=X.Y.Z` dispatches the full publishing pipeline for the explicitly prepared version.

The publishing pipeline is not Play-only: it can publish GitLab/GitHub artifacts and deploy web content in addition to Play. Confirm that scope before dispatch. The release launcher requires a clean tree, a protected GitLab branch, matching remote commit, and consistent `fdroid/version.properties` values. The direct bundle builder runs `flutter clean` before `pub get` by default, which deletes ignored outputs under `build/`; inspect and preserve any needed capture/test evidence first. When dependencies are already current, `scripts/build-play-console.sh --skip-pub-get` skips both clean and pub-get and builds with `--no-pub`; use it only after confirming the package configuration is ready.

## Production track configuration

The repository's GitLab release configuration defaults Play to `PLAY_TRACK=internal` and `PLAY_RELEASE_STATUS=draft`. Production requires protected GitLab variables `PLAY_TRACK=production` and `PLAY_RELEASE_STATUS=completed`. Confirm their effective values using authenticated GitLab access before the publish pipeline; never assume the YAML default or the user's local shell environment will override project variables. Treat an unsuccessful auth/API read as unknown. A permanent variable update can make later releases publish to production too, so obtain authorization and preserve/restore existing values if changing project configuration.

The direct `scripts/build-upload-playstore.sh` path can build and upload a bundle outside the full platform pipeline. Do not silently use it to route around missing GitLab access or failed gates. If the owner explicitly chooses Play-only and waives the full pipeline, use the direct path, disclose the reduced provenance/testing coverage, run the available local checks, and keep waived CI results marked unknown. Do not continue treating the explicitly waived GitLab route as a blocker.

## Rollout and recovery

This repository's upload path accepts `completed` or `draft`; `production` with `completed` is a full rollout, not a percentage rollout. Do not report it as staged. Before publication, record the health signal, numeric threshold, observation window, recovery owner, and exact action. Once a completed release is installed, recovery requires shipping a corrected higher-version build; do not promise that users can be downgraded to the prior code.

## Evidence boundaries

- `./release.sh --dry-run` proves only that the local script selected a plan.
- A prepare pipeline proves only the gates it actually completed; it does not prove publication.
- An upload receipt proves the store accepted the recorded upload at its timestamp; verify current track state before claiming it is still live.
- The direct uploader does not automatically publish `fastlane/metadata/android/<locale>/changelogs/<code>.txt`; inspect the committed track release's `releaseNotes` field and report notes as unpublished unless a readback confirms them.
- A temporary `hermes-verify-` script can check marker/build consistency, release-note bounds, changelog headings, and dry-run selection when no canonical test exists. Remove it after execution and label the result *ad-hoc*, not suite-green.
