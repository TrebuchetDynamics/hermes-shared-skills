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
--enable           Enable newly installed and already present plugins.
--yes-deps         Consent to declared Python dependencies on native installs.
--setup            Configure OMH and isolated Hindsight memory using bundle defaults.
--hindsight-config FILE
                   Connection-only JSON for new Hindsight profiles (no credentials).
--bundle-only      Link and enable this bundle in every live profile and apply
                   its defaults, without installing external sources.
--hermes-home ROOT Select the default Hermes home containing profiles/.
                   Defaults to HERMES_HOME (or ~/.hermes); a named-profile
                   HERMES_HOME is resolved to its containing root.
EOF
}

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

dry_run=false
enable=false
yes_deps=false
setup=false
bundle_only=false
hindsight_config=''
hermes_root=${HERMES_HOME:-"$HOME/.hermes"}
if [[ $(basename -- "$(dirname -- "$hermes_root")") == profiles ]]; then
    hermes_root=$(dirname -- "$(dirname -- "$hermes_root")")
fi
while (($#)); do
    case $1 in
        --dry-run) dry_run=true; shift ;;
        --enable) enable=true; shift ;;
        --yes-deps) yes_deps=true; shift ;;
        --setup) setup=true; shift ;;
        --bundle-only) bundle_only=true; setup=true; shift ;;
        --hindsight-config)
            [[ $# -ge 2 && -n $2 ]] || die '--hindsight-config requires a JSON file'
            hindsight_config=$2; shift 2 ;;
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
apply_bundle_defaults() {
    local profile=$1 key value errors=0
    while IFS=$'\t' read -r key value; do
        if $dry_run; then
            printf 'Plan: config %s=%s (%s)\n' "$key" "$value" "$profile"
            [[ $key != approvals.mode ]] || printf 'Plan: command approvals=%s (%s)\n' "$value" "$profile"
        elif ! HERMES_HOME=$hermes_root hermes -p "$profile" config set "$key" "$value"; then
            errors=$((errors + 1))
        fi
    done <<< "$bundle_defaults"
    ((errors == 0))
}
bundle_defaults=''
if $setup; then
    bundle_defaults=$(python3 - "$script_dir/plugins/defaults.json" <<'PYDEFAULTS'
import json, sys
cfg = json.load(open(sys.argv[1]))['hermes']
assert cfg['approvals_mode'] in ('off', 'manual', 'smart'), 'Invalid command approval default'
for key in ('allow_gateway_injection', 'destructive_slash_confirm', 'mcp_reload_confirm'):
    assert type(cfg[key]) is bool, 'Invalid boolean default: ' + key
assert isinstance(cfg['skills_disabled'], list) and isinstance(cfg['skills_platform_disabled'], dict)
for setting, key in (
    ('plugins.entries.hermes-toolset.allow_gateway_injection', 'allow_gateway_injection'),
    ('approvals.mode', 'approvals_mode'),
    ('approvals.destructive_slash_confirm', 'destructive_slash_confirm'),
    ('approvals.mcp_reload_confirm', 'mcp_reload_confirm'),
    ('skills.disabled', 'skills_disabled'),
    ('skills.platform_disabled', 'skills_platform_disabled')):
    value = cfg[key]
    print(setting + '\t' + (value if isinstance(value, str) else json.dumps(value)))
PYDEFAULTS
    ) || die 'Invalid bundle defaults'
fi
temp_dir=''
trap '[[ -z $temp_dir ]] || rm -rf -- "$temp_dir"' EXIT
if $setup; then
    [[ -f $script_dir/plugin.yaml ]] || die 'Bundle plugin.yaml is missing'
    for profile in "${profiles[@]}"; do
        profile_dir=$hermes_root
        [[ $profile == default ]] || profile_dir=$hermes_root/profiles/$profile
        target=$profile_dir/plugins/hermes-toolset
        if [[ -e $target || -L $target ]]; then
            if [[ ! -f $target/plugin.yaml ]]; then
                printf 'Error: existing bundle path is not a plugin: %s\n' "$target" >&2
                failed=$((failed + 1))
                continue
            fi
        elif $dry_run; then
            printf 'Plan: link hermes-toolset into %s\n' "$profile"
        else
            mkdir -p -- "$profile_dir/plugins"
            ln -s -- "$script_dir" "$target"
        fi
        if ! apply_bundle_defaults "$profile"; then
            failed=$((failed + 1))
            continue
        fi
        if $dry_run; then
            printf 'Plan: enable hermes-toolset (%s)\n' "$profile"
        elif ! HERMES_HOME=$hermes_root hermes -p "$profile" plugins enable hermes-toolset; then
            failed=$((failed + 1))
        fi
    done
fi
for ((i=0; i<${#plugins[@]}; i++)); do
    $bundle_only && break
    plugin=${plugins[i]}
    source=${sources[i]}
    targets=(default)
    [[ ${scopes[i]} != 'all profiles' ]] || targets=("${profiles[@]}")
    if [[ $plugin == hindsight ]]; then
        hindsight_args=(python3 "$script_dir/install-hindsight.py" --hermes-home "$hermes_root")
        for profile in "${targets[@]}"; do hindsight_args+=(--profile "$profile"); done
        [[ -z $hindsight_config ]] || hindsight_args+=(--config "$hindsight_config")
        $dry_run && hindsight_args+=(--dry-run)
        # Native plugin installation can select memory.provider immediately.
        # Prepare every isolated bank before any plugin is allowed to activate.
        if ! "${hindsight_args[@]}" --prepare; then
            failed=$((failed + 1))
            continue
        fi
    fi
    if [[ ${source,,} == https://github.com/graphify-labs/graphify ]]; then
        helper_args=(python3 "$script_dir/install-graphify.py" --hermes-home "$hermes_root")
        for profile in "${targets[@]}"; do helper_args+=(--profile "$profile"); done
        $dry_run && helper_args+=(--dry-run)
        if "${helper_args[@]}"; then
            $dry_run && planned=$((planned + 1)) || installed=$((installed + 1))
        else
            failed=$((failed + 1))
        fi
        continue
    fi
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
            for profile in "${targets[@]}"; do
                profile_dir=$hermes_root
                [[ $profile == default ]] || profile_dir=$hermes_root/profiles/$profile
                python3 - "$script_dir" "$profile_dir" "$source" "${skill_files[@]}" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from bundle import record_skill_repository
record_skill_repository(sys.argv[2], sys.argv[3], [Path(p).parent.name for p in sys.argv[4:]])
PY
            done
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
                    if HERMES_HOME=$hermes_root hermes -p "$profile" skills install "${source#https://github.com/}/skills/$skill_name" --yes; then
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
    source_failed=false
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
                source_failed=true
                continue
            fi
        fi
        if [[ -n $target && ( -e $target || -L $target ) ]]; then
            if [[ -f $target/plugin.yaml || -f $target/plugin.json || -f $target/__init__.py ]]; then
                printf 'Skip: %s (%s) already present\n' "$plugin" "$profile"
                skipped=$((skipped + 1))
                if $enable; then
                    if $dry_run; then
                        printf 'Plan: enable %s (%s)\n' "${target##*/}" "$profile"
                    elif ! HERMES_HOME=$hermes_root hermes -p "$profile" plugins enable "${target##*/}"; then
                        failed=$((failed + 1))
                        source_failed=true
                    fi
                fi
            else
                printf 'Failed: %s (%s): existing path is not a plugin: %s\n' "$plugin" "$profile" "$target" >&2
                failed=$((failed + 1))
                source_failed=true
            fi
            continue
        fi
        command_args=(hermes -p "$profile" plugins install "$source")
        $enable && command_args+=(--enable)
        $yes_deps && command_args+=(--yes-deps)
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
                source_failed=true
            fi
        fi
    done
    if $setup && ! $source_failed && [[ $plugin == omh ]]; then
        helper_args=(python3 "$script_dir/install-omh.py" --hermes-home "$hermes_root")
        for profile in "${targets[@]}"; do helper_args+=(--profile "$profile"); done
        $dry_run && helper_args+=(--dry-run)
        if ! "${helper_args[@]}"; then
            failed=$((failed + 1))
        fi
    fi
    if $setup && ! $source_failed && [[ $plugin == hindsight ]]; then
        if ! "${hindsight_args[@]}"; then
            failed=$((failed + 1))
        fi
    fi
done
if $setup && ! $bundle_only; then
    for profile in "${profiles[@]}"; do
        profile_dir=$hermes_root
        [[ $profile == default ]] || profile_dir=$hermes_root/profiles/$profile
        if [[ -f $profile_dir/plugins/hermes-toolset/plugin.yaml ]] || $dry_run; then
            apply_bundle_defaults "$profile" || failed=$((failed + 1))
        fi
    done
fi
printf 'Sources: %s install commands succeeded, %s planned, %s skipped, %s failed\n' "$installed" "$planned" "$skipped" "$failed"
((failed == 0))
