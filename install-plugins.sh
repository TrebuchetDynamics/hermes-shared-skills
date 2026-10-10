#!/usr/bin/env bash
# Install plugin and skill sources declared in plugins/PLUGINS.md.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./install-plugins.sh [--dry-run] [--hermes-home ROOT]

Reads plugins/PLUGINS.md beside this script. Each non-comment line is:
  https://hermes-agent.nousresearch.com/docs/plugins/NAME all profiles
  https://hermes-agent.nousresearch.com/docs/plugins/NAME default profile only
  https://github.com/OWNER/REPO all profiles
  skills https://github.com/OWNER/REPO all profiles

Installs missing plugins using Hermes' normal installation/activation prompts.
Existing installs are skipped, never force-replaced. No gateways are restarted.
--dry-run          Print commands without invoking Hermes or changing profiles.
--hermes-home ROOT Select the default Hermes home containing profiles/.
                   Defaults to HERMES_HOME (or ~/.hermes); a named-profile
                   HERMES_HOME is resolved to its containing root.
EOF
}

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

dry_run=false
hermes_root=${HERMES_HOME:-"$HOME/.hermes"}
if [[ $(basename -- "$(dirname -- "$hermes_root")") == profiles ]]; then
    hermes_root=$(dirname -- "$(dirname -- "$hermes_root")")
fi
while (($#)); do
    case $1 in
        --dry-run) dry_run=true; shift ;;
        --hermes-home)
            [[ $# -ge 2 && -n $2 ]] || die '--hermes-home requires a directory'
            hermes_root=$2; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown option: $1" ;;
    esac
done

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
manifest=$script_dir/plugins/PLUGINS.md
[[ -r $manifest ]] || die "Cannot read $manifest"
[[ -d $hermes_root ]] || die "Hermes home does not exist: $hermes_root"
hermes_root=$(cd -- "$hermes_root" && pwd -P)

# Validate every entry before the first install; never evaluate manifest text.
plugins=()
sources=()
kinds=()
scopes=()
line_number=0
entry_pattern='^[[:space:]]*https://hermes-agent\.nousresearch\.com/docs/plugins/([a-z0-9][a-z0-9_-]*)/?[[:space:]]+(all profiles|default profile only)[[:space:]]*$'
github_pattern='^[[:space:]]*(skills[[:space:]]+)?https://github\.com/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)(\.git)?/?[[:space:]]+(all profiles|default profile only)[[:space:]]*$'
while IFS= read -r line || [[ -n $line ]]; do
    line_number=$((line_number + 1))
    line=${line%$'\r'}
    [[ $line =~ ^[[:space:]]*(#.*)?$ ]] && continue
    kind=plugin
    if [[ $line =~ $entry_pattern ]]; then
        plugin=${BASH_REMATCH[1]}
        source=$plugin
        scope=${BASH_REMATCH[2]}
    elif [[ $line =~ $github_pattern ]]; then
        [[ -z ${BASH_REMATCH[1]} ]] || kind=skills
        source=https://github.com/${BASH_REMATCH[2]}/${BASH_REMATCH[3]}
        plugin=${BASH_REMATCH[3]}
        scope=${BASH_REMATCH[5]}
    else
        die "Invalid manifest entry at line $line_number: expected catalog/GitHub URL and profile scope (optional skills prefix)"
    fi
    duplicate=false
    for ((i=0; i<${#plugins[@]}; i++)); do
        if [[ ${kinds[i]} == "$kind" && ${plugins[i]} == "$plugin" ]]; then
            [[ ${sources[i]} == "$source" ]] || die "Conflicting sources for $plugin at line $line_number"
            [[ ${scopes[i]} == "$scope" ]] || die "Conflicting scopes for $plugin at line $line_number"
            duplicate=true
        fi
    done
    if ! $duplicate; then
        plugins+=("$plugin")
        sources+=("$source")
        kinds+=("$kind")
        scopes+=("$scope")
    fi
done < "$manifest"
((${#plugins[@]})) || die 'The plugin manifest is empty'

# Mirror Hermes' identity-marker and tombstone rules without booting the CLI
# or reading profile configuration/secrets just to enumerate directories.
profiles=(default)
shopt -s nullglob
for profile_dir in "$hermes_root"/profiles/*; do
    [[ -d $profile_dir ]] || continue
    profile=${profile_dir##*/}
    [[ $profile != default && $profile =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || continue
    [[ ! -e $hermes_root/profiles/.deleted/$profile ]] || continue
    for marker in config.yaml .env SOUL.md profile.yaml auth.json state.db; do
        if [[ -f $profile_dir/$marker || -L $profile_dir/$marker ]]; then
            profiles+=("$profile")
            break
        fi
    done
done

if ! $dry_run; then
    command -v hermes >/dev/null 2>&1 || die 'hermes is not on PATH'
fi
failed=0
installed=0
skipped=0
planned=0
temp_dir=''
trap '[[ -z $temp_dir ]] || rm -rf -- "$temp_dir"' EXIT
for ((i=0; i<${#plugins[@]}; i++)); do
    plugin=${plugins[i]}
    source=${sources[i]}
    # Graphify v8 ships a Python CLI and generated host-specific skills, not a
    # Hermes plugin manifest or a standard skills/*/SKILL.md bundle.
    if [[ ${source,,} == https://github.com/graphify-labs/graphify ]]; then
        printf 'Unsupported: Graphify is a CLI, not a Hermes plugin; it needs a separate Hermes integration: %s\n' "$source" >&2
        failed=$((failed + 1))
        continue
    fi
    targets=(default)
    [[ ${scopes[i]} != 'all profiles' ]] || targets=("${profiles[@]}")
    if [[ ${kinds[i]} == skills ]]; then
        if $dry_run; then
            for profile in "${targets[@]}"; do
                printf 'Plan: discover %s/skills/*/SKILL.md and install skills into %s (no network in dry-run)\n' "$source" "$profile"
                planned=$((planned + 1))
            done
            continue
        fi
        temp_dir=$(mktemp -d)
        if ! git clone --quiet --depth 1 -- "$source" "$temp_dir/repo"; then
            printf 'Failed: cannot clone skill repository %s\n' "$source" >&2
            failed=$((failed + 1))
        else
            skill_files=("$temp_dir"/repo/skills/*/SKILL.md)
            if ((${#skill_files[@]} == 0)); then
                printf 'Failed: no skills/*/SKILL.md found in %s\n' "$source" >&2
                failed=$((failed + 1))
            fi
            for skill_file in "${skill_files[@]}"; do
                skill_name=${skill_file%/SKILL.md}
                skill_name=${skill_name##*/}
                if [[ -L $skill_file || -L ${skill_file%/SKILL.md} || ! $skill_name =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
                    printf 'Failed: unsupported skill path %s\n' "$skill_name" >&2
                    failed=$((failed + 1))
                    continue
                fi
                for profile in "${targets[@]}"; do
                    printf 'Installing skill: %s (%s)\n' "$skill_name" "$profile"
                    if HERMES_HOME=$hermes_root hermes -p "$profile" skills install "${source#https://github.com/}/skills/$skill_name"; then
                        installed=$((installed + 1))
                    else
                        printf 'Failed: skill %s (%s)\n' "$skill_name" "$profile" >&2
                        failed=$((failed + 1))
                    fi
                done
            done
        fi
        rm -rf -- "$temp_dir"
        temp_dir=''
        continue
    fi
    for profile in "${targets[@]}"; do
        profile_dir=$hermes_root
        [[ $profile == default ]] || profile_dir=$hermes_root/profiles/$profile
        target=$profile_dir/plugins/$plugin
        if [[ $source == https://github.com/* ]]; then
            # Hermes installs under the manifest name, not necessarily the repo name.
            if ! target=$(python3 - "$profile_dir" "$source" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]) / 'plugins'
metadata = root / '.install-metadata.json'
try:
    records = json.loads(metadata.read_text()) if metadata.exists() else {}
    if not isinstance(records, dict):
        raise ValueError('expected object')
    for name, record in records.items():
        if not isinstance(record, dict):
            raise ValueError('expected install record')
        source = record.get('source', '')
        if isinstance(source, str) and source.rstrip('/').removesuffix('.git').lower() == sys.argv[2].lower():
            if not name or Path(name).name != name or name in ('.', '..'):
                raise ValueError('invalid installed plugin name')
            print(root / name)
            break
except (OSError, ValueError):
    print('Cannot read plugin install provenance', file=sys.stderr)
    sys.exit(1)
PY
            ); then
                printf 'Failed: %s (%s): could not resolve installed source\n' "$plugin" "$profile" >&2
                failed=$((failed + 1))
                continue
            fi
        fi
        if [[ -n $target && ( -e $target || -L $target ) ]]; then
            if [[ -f $target/plugin.yaml || -f $target/plugin.json || -f $target/__init__.py ]]; then
                printf 'Skip: %s (%s) already present\n' "$plugin" "$profile"
                skipped=$((skipped + 1))
            else
                printf 'Failed: %s (%s): existing path is not a plugin: %s\n' "$plugin" "$profile" "$target" >&2
                failed=$((failed + 1))
            fi
            continue
        fi
        command_args=(hermes -p "$profile" plugins install "$source")
        if $dry_run; then
            printf 'HERMES_HOME=%q ' "$hermes_root"
            printf '%q ' "${command_args[@]}"
            printf '\n'
            planned=$((planned + 1))
        else
            printf 'Installing: %s (%s)\n' "$plugin" "$profile"
            if HERMES_HOME=$hermes_root "${command_args[@]}"; then
                installed=$((installed + 1))
            else
                printf 'Failed: %s (%s)\n' "$plugin" "$profile" >&2
                failed=$((failed + 1))
            fi
        fi
    done
done
printf 'Sources: %s install commands succeeded, %s planned, %s skipped, %s failed\n' "$installed" "$planned" "$skipped" "$failed"
((failed == 0))
