#!/usr/bin/env bash
# Install local skills, then declared plugins, forwarding all arguments.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
installers=(install-skills.sh install-plugins.sh)

for installer in "${installers[@]}"; do
    if [[ ! -f $script_dir/$installer || ! -r $script_dir/$installer ]]; then
        printf 'Error: cannot read %s\n' "$script_dir/$installer" >&2
        exit 1
    fi
done

failed=0
for installer in "${installers[@]}"; do
    printf 'Running %s\n' "$installer"
    if bash "$script_dir/$installer" "$@"; then
        printf 'Completed %s\n' "$installer"
    else
        status=$?
        printf 'Failed: %s (exit %s)\n' "$installer" "$status" >&2
        failed=1
    fi
done

exit "$failed"
