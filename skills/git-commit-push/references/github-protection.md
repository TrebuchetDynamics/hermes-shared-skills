# GitHub protection changes

Use only when an owner explicitly authorizes a named protection change. A ship or
merge request alone does not authorize changing repository security policy.

## Remove a PR requirement without disabling protection

1. Inspect effective branch rules:
   `gh api repos/<owner>/<repo>/rules/branches/<branch>`.
   Identify every ruleset contributing a `pull_request` rule; do not infer that
   one repository ruleset is the only source of protection.
2. Read each exact authorized ruleset:
   `gh api repos/<owner>/<repo>/rulesets/<ruleset-id>`.
   Retain its pre-change response as private evidence. If the rule is organization
   owned or legacy branch protection, inspect that authority instead of editing an
   unrelated repository ruleset.
3. Construct the update from the fresh response, keeping writable fields `name`,
   `target`, `enforcement`, `conditions`, `bypass_actors` and `rules`. Remove only
   entries whose `type` is `pull_request`; preserve other rule parameters exactly.
   Omit read-only response metadata. Never set enforcement to disabled or add a
   bypass actor as a substitute for removing the requested rule.
4. Submit the JSON through stdin:
   `gh api --method PUT repos/<owner>/<repo>/rulesets/<ruleset-id> --input -`.
   Preserve all remaining rules because replacing the rules array can otherwise
   silently remove force-push, deletion or status-check protection.
5. Read back both the exact ruleset and effective branch rules. Assert that retained
   fields and rules match the intended payload and that no effective `pull_request`
   rule remains. A successful PUT alone does not prove the branch route changed;
   inherited protection may still apply.
6. Resolve the policy question in its existing ledger entry with readback evidence.
   Report the removed requirement and retained protections, without claiming any
   code was shipped. Resume the existing delivery obligation with its original
   candidate checks; protection changes do not waive test gates.

If effective protection still requires PRs, report the remaining source and continue
independent validation. Do not broaden the policy mutation beyond the owner's scope.
