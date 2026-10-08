# Team setup: skills, commands, and optional voice

This repository is the portable toolset, not a copy of a teammate's Hermes home.
Share the Git checkout. Keep credentials, sessions, memories, SOUL identity, audio,
and project-specific configuration on each machine. Do not commit `.env`,
`auth.json`, or a populated `config.yaml`.

## Install only the shared skills

Supported scope: Linux with an existing Hermes installation. This is not a
clean-machine or macOS/Windows certification.

Prerequisites: Hermes installed and configured for your own account, Python 3.12+,
Bash, and Git. Use the [official Hermes setup](https://hermes-agent.nousresearch.com/docs/).
Clone this repository into a stable local path, then run from its root:

```sh
./install.sh --profiles default --dry-run
./install.sh --profiles default
hermes skills list --enabled-only
```

The installer adds the checkout to `skills.external_dirs` and writes managed
script wrappers. These minimal flags do not install vendors, schedule jobs,
change approval policy, prune skills, or replace your identity. Inspect its
preview first. An existing config is required: the installer skips missing
profiles rather than creating them. Use `--profiles alice,bob` only for existing
profiles you own under the selected Hermes home. Do not copy someone else's
profile directory to create yours. Profile IDs cannot be paths. Symlinked
profiles or managed write targets outside the selected profile are refused before
any profile is changed. Concurrent configuration writers are not supported.

The full `bootstrap.sh` and `new_profile.sh` are fleet setup, not this minimal
team setup. They opt into permissive approvals and other fleet conventions;
bootstrap also schedules jobs. Review the [runbook](../runbook.md) before use.
OMH and vendored skills are separate opt-in dependencies.

## Commands and updates

A first-party `<name>/SKILL.md` supplies a skill command. See the
[command catalog](../README.md#commands); for example `/repo-docs`, `/grill-me`,
and `/git-pull-merge`. Telegram normalizes hyphens (`/repo_docs`). A menu entry
alone does not prove command discovery. After wiring or pulling an update,
check `skills.external_dirs` and start a fresh session to check discovery:

```sh
hermes config get skills.external_dirs --json
hermes skills list --enabled-only
```

Run the same commands with `hermes -p NAME` for a named profile. Local skills
with the same name may shadow shared skills. Do not delete them automatically;
inspect the resolved source before removing a duplicate. Do not restart active
workers merely to refresh a cached skill index. Update through the scoped
`/git-pull-merge` workflow and rerun the offline checks before team adoption.

### Relocate a checkout

Run from the new checkout. Name the previous root explicitly; the installer does
not guess which external skill directory belongs to this repository:

```sh
./install.sh --profiles default --replace-root /absolute/old-checkout --dry-run
./install.sh --profiles default --replace-root /absolute/old-checkout
```

Only the matching old discovery root is replaced. Other external directories,
settings, identity and jobs remain. Generated wrappers are refreshed; customized
wrappers remain unchanged and are reported. Update their custom logic yourself
if it refers to the old location. Local first-party shadows are reported, not
removed. A second installation with the same options is byte-idempotent.

## Optional local speech-to-text

The default for this guide is to preserve existing voice settings. To opt in,
pass the exact target home to the helper. It previews unless `--apply` is given:

```sh
python extras/install/configure_stt.py --home "$HOME/.hermes" --provider local
python extras/install/configure_stt.py --home "$HOME/.hermes" --provider local --model base --apply
```

For a named profile, use its actual home, such as
`$HOME/.hermes/profiles/myproject`, instead. The helper uses `hermes config set`
and JSON readback, never edits YAML directly. It changes only `stt.enabled`,
`stt.provider`, and `stt.local.model`. Each CLI operation has a 30-second timeout;
it stops on the first failure and does not retry mutations. The sequence is not
atomic: earlier settings may remain if a later call fails. Inspect those three
keys on the target and rerun only after fixing the reported failure. Concurrent
configuration writers are not supported.

To disable transcription without deleting model/provider preferences:

```sh
python extras/install/configure_stt.py --home "$HOME/.hermes" --provider off --apply
```

Local recognition requires the Hermes `stt-whisper` dependency and model files.
The helper deliberately installs neither; model downloads require network and
disk space. Follow the current [voice configuration documentation](https://hermes-agent.nousresearch.com/docs/user-guide/configuration).
Configuration readback is not proof of dependency readiness or transcription.
Verify recognition with a non-sensitive recording on each target machine before
relying on it. This pass does not certify provider fallback behavior; review
runtime behavior before using sensitive audio. Cloud STT, credentials, and paid
providers are outside this helper's scope. No audio is processed by setup.

### Offline readiness and opt-in audio check

Use an interpreter with the already-installed `faster_whisper` dependency and an
existing converted model directory. This check never installs or downloads:

```sh
python extras/install/local_stt.py --model-dir /absolute/cached-model
```

Exit 2 means a dependency or required model file is missing. A ready result means
files and dependency discovery passed, not that model loading or recognition did.
To test approved non-sensitive audio, declare the expected phrase and bound the
Linux process runtime:

```sh
timeout 120s python extras/install/local_stt.py --model-dir /absolute/cached-model \
  --audio /absolute/non-sensitive.wav --transcribe --non-sensitive \
  --expect 'the expected spoken phrase'
```

The smoke uses CPU local inference directly, local-files-only loading, offline
flags and socket denial. It does not use Hermes' provider dispatch or fallback.
Phrase matching ignores case and punctuation. No transcript is printed. Failure
or timeout is not a passing audio check. No automatic retries occur. Actual audio
acceptance remains NOT_RUN when the installed dependency or cached model is absent.

## Verification and reusable change procedure

```sh
python extras/install/test_configure_stt.py
python scripts/check.py
# Optional: installed Hermes required; temporary isolated home, no inference.
python extras/install/smoke_stt.py
python extras/install/smoke_discovery.py --agent-dir /absolute/installed-hermes-source
```

For each future toolset change: inspect the saved progress note and dirty tree;
write observable checks before implementation; add a failing regression; fix
and rerun it; run the full offline gate; review the saved diff; record failures,
reruns, review duration, and measured usage in `checks.md`; update `progress.md`
with exact paths and one next action. Keep real-CLI smoke tests separate from
offline CI and keep provider execution separate from configuration evidence.
Never infer cost savings or mark tests as passed merely because they exist.
