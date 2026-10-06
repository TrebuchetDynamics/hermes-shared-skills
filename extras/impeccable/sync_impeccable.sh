#!/usr/bin/env bash
# Kept for compatibility: impeccable is now one entry in extras/vendor/manifest.json.
exec python3 "$(cd "$(dirname "$0")/.." && pwd)/vendor/sync_vendor.py" --only impeccable "$@"
