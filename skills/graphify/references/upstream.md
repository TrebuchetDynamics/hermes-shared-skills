# Upstream provenance

- Canonical repository: https://github.com/Graphify-Labs/graphify
- Reviewed branch: `v8`
- Reviewed source commit: `6478eb71237c86ee5fb6a35c702835e987ca445d`
- Package and CLI tested: `graphifyy==0.9.80`, executable `graphify`
- Upstream license: Apache-2.0, with upstream license/notice files included in the installed package. This directory contains an original MIT-licensed Hermes adapter, not vendored upstream code or skill text.

Reviewed interfaces: upstream `README.md` (installation and official package identity), `pyproject.toml` (Python floor, dependency isolation and entry points), `graphify/__main__.py` (CLI help), and `graphify/cli.py` (code-only extraction, output root, raw graph generation, and cluster-only flow).

The upstream Hermes installer writes a profile-local skill and may add always-on context. We intentionally do not run it: the canonical adapter lives here and is discovered through each profile's configured shared external directory.

Default sequence:

1. `graphify extract <source> --code-only --no-cluster --max-workers 2 --out <fresh-output-root>`
2. `graphify cluster-only <fresh-output-root> --no-label`
3. Query the explicit `<fresh-output-root>/graphify-out/graph.json`.

The no-cluster extraction avoids the semantic/labeling path, and no-label clustering disables LLM naming. Existing output is refused because upstream code-only incremental extraction can retain old semantic content. No live database, global graph, watcher, hooks, platform installer, provider configuration, or model invocation is part of this adapter.

The package and source are separate provenance checks: a PyPI version install is not proof that every installed byte equals this Git commit. Record both and do not claim binary reproducibility or exhaustive upstream security review.
