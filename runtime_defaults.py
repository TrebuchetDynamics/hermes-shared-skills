"""Apply the bundle's approval policy in the profile bound by Hermes' loader."""


def apply_runtime_defaults(ctx):
    # This opt-out must be set before restoring prompts; otherwise the next load
    # deliberately reapplies the bundle policy.
    if ctx.get_config('apply_runtime_defaults', True) is False:
        return

    from hermes_cli.config import require_readable_config_before_write, save_config
    from .bundle import defaults

    wanted = defaults()['hermes']
    patch = {
        'approvals': {
            'mode': wanted['approvals_mode'],
            'destructive_slash_confirm': wanted['destructive_slash_confirm'],
            'mcp_reload_confirm': wanted['mcp_reload_confirm'],
        },
        'plugins': {'entries': {'hermes-toolset': {
            'allow_gateway_injection': wanted['allow_gateway_injection'],
        }}},
    }
    # Read raw YAML, refusing malformed settings rather than overwriting them
    # with fallback defaults. The native loader binds the owning profile even
    # when a shared gateway loads several profiles in the same process.
    raw = require_readable_config_before_write()
    paths = set()

    def differs(current, expected, prefix=()):
        changed = False
        for key, value in expected.items():
            path = prefix + (key,)
            actual = current.get(key) if isinstance(current, dict) else None
            if isinstance(value, dict):
                changed = differs(actual, value, path) or changed
            else:
                paths.add(path)
                changed = type(actual) is not type(value) or actual != value or changed
        return changed

    if differs(raw, patch):
        # Merge under Hermes' config lock, preserving unrelated settings and
        # deny rules. Keep false values explicit even if upstream defaults change.
        save_config(patch, merge_existing=True, preserve_keys=paths)
