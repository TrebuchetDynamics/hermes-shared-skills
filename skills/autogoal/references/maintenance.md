# Autogoal — Skill maintenance and verification

Load only when editing this skill or its scripts (interactive, owner-authorized sessions). The Operating priorities in SKILL.md override anything here.

## Verification

### Executable candidate safeguards

Qualify an immutable assembled commit with `scripts/check_receipt.py run --base <full-id> --candidate <ref-or-id> --tree <tree-id> --prerequisite <ref>=<full-id>` and explicit paths/platform/backend/mode/toolchain. Pin every required sibling and reject missing ancestry before checking; never upgrade shared dirty-tree evidence to isolated-branch qualification. Gate a complete temporary-index candidate, then protect the passing tree with a local agent branch without moving shared HEAD/index.

Require helper-backed reusable receipts in delivery-state evaluation; asserted pass/live fields are not executed proof. Derive scope from the receipt, preserve current run/card ownership, and never auto-close a product milestone from a delivered slice. Protected-PR issuer claims and local main ancestry still require actual remote readback before human delivery claims.

Keep generated-output and unconfined-command receipts weaker than exact qualification. Reject undeclared untracked additions and visibly shared-checkout-dependent embedded commands. The helper is a dependency-declared snapshot, not a filesystem sandbox or read tracer; trusted check scripts must not create transient undeclared source dependencies. Run receipt/identity/state/reconcile regressions together after boundary changes.

For native lifecycle probes, isolate both `HERMES_HOME` and `HERMES_KANBAN_HOME` and remove inherited routing pins. Native CLI/database idempotency is not worker execution or review acknowledgement. Snapshot all prior run IDs before every dispatch; require fresh ended runs, supported linked claim/outcome events and exact artifact readback while preserving original contract and ended history. Pass remaining total time to every transport call and reject results returned after the deadline. Exercise actual failure/timeout and retry-exhaustion paths in explicitly labeled fixtures rather than reopening only successful review. A fixture-only flag or Python type check is not an execution capability. Native workers can detach into new sessions/systemd scopes; use the containment procedure below before treating a CLI timeout as worker cancellation. Require real externally enforced model-spending controls before live execution; turn caps, session cost filters and included-price accounting are not monetary caps.

### Native descendant containment probes

1. Discover the host's actual user-cgroup and namespace capabilities before choosing a launcher: inspect `/proc/self/cgroup` and `/sys/fs/cgroup/cgroup.controllers`, resolve `systemd-run` and `bwrap`, and query `systemctl --user show --property=Version`. Probe user-space support without sudo or live-profile changes; binary presence alone does not prove execution support.
2. Run a disposable local Python process in a uniquely named transient user service. Bound both the controller subprocess and the service. A working service recipe uses `systemd-run --user --wait --collect --quiet --unit=<unique-unit> --property=RuntimeMaxSec=2s --property=TimeoutStopSec=1s --property=KillMode=control-group --property=MemoryMax=128M --property=TasksMax=16 --property=CPUQuota=100% --property=NoNewPrivileges=yes <python> <probe>`. Make the probe spawn a sleeping child with `start_new_session=True`, then sleep itself. Record the exact argv, elapsed time, service result and independently observed descendant state; a runtime-limited service can return nonzero while its cleanup assertions pass.
3. Combine the service with `bwrap --unshare-user --unshare-pid --unshare-net --die-with-parent --ro-bind / / --proc /proc --dev /dev --tmpfs /run --bind <scratch> <scratch> --clearenv --setenv PATH /usr/bin:/bin -- <python> <probe>`. Substitute observed absolute paths and use only disposable local payloads. Assert the host user-manager bus is hidden, `systemd-run --user` dispatch fails, and only loopback interfaces remain. Denying manager access matters because a new scope/service can move work outside the controller's cgroup; killing a process group does not stop that escape.
4. After the sandbox marker confirms the detached child exists, obtain the exact service `ControlGroup` through `systemctl --user show <unique-unit> --property=ControlGroup --value` and capture host PIDs from its `cgroup.procs` before timeout. Verify those host PIDs are absent or non-running afterward; account for PID reuse when strengthening this into a reusable verifier. Never check sandbox-reported PIDs against the host `/proc`: PID namespaces assign different identities. On controller errors, stop only the uniquely owned transient unit and reap its launcher under a bounded cleanup timeout.
5. Preserve raw receipts and distinguish local containment capability, native worker acceptance and spending enforcement. A combined local probe can prove detached-process cleanup and manager denial without proving a real dispatch/recovery/review journey. Resource properties being set do not prove memory/CPU/pid exhaustion behavior. Read-only host root still exposes readable home/credential files; replace it with a least-privilege filesystem and isolated home/board/repository before real workers run. Network isolation deliberately prevents direct provider access; keep native execution fail-closed until a vetted controller-only bridge and hard spending enforcement are integrated and exercised.

Keep installed-native-CLI control suites opt-in even when they make zero model calls: zero spend does not make a test hermetic or independent of host CLI setup. Inspect recursive default test discovery when adding such a suite. First add a failing discovery regression asserting its exclusion, then implement the exclusion and run that regression, the native controls explicitly, and the canonical offline gate separately. Report offline, model-backed and opt-in native suite counts independently; a green control suite never satisfies actual worker-run/review acceptance.


For milestone-first changes, exercise the real `goals.py focus <repo> <GOAL>` write,
`focus <repo> --json` read and `next <repo> --json` ordering. Run
`repo-docs/scripts/test_milestone_focus.py` and `test_goals.py`; dependencies remain
mandatory and focused Next must precede unrelated Now. Inspect the generated
`start_goal.py` worker body as well as skill prose: injected delivery/review rules
must agree with policy. Run `autogoal/scripts/test_workflow_handoff.py` plus the
existing handoff and picker-policy regressions. Update stale policy assertions
only when the accepted contract changed, preserving no-bypass, original-card and
mandatory-review checks. Tests of policy text do not prove observed worker behavior.
For a suite exceeding the terminal transport's foreground window, use a bounded
background command with completion notification and a saved exact-command/exit/log
receipt. Read that receipt and terminal test summary after notification. Do not
restart an unchanged suite or poll it each turn. A transport-interrupted run is
not a completed failure/pass receipt; distinguish earlier test failures from
shutdown errors. Product-test success still does not prove live/platform delivery.

Separate maintenance verification from product qualification: record each command,
source snapshot, dependency/environment identity, exit status and measured duration
under its actual scope. A shared-skill gate is not the application's complete gate;
run the repository's prescribed gate when requested and report its result separately.
Do not label a candidate frozen while repair workers can still modify its source.
After repairs, capture the final candidate identity before the integration gate.
Reuse unchanged behavior evidence across report/checkpoint edits, but invalidate it
when relevant source, dependencies or environment change. Save reusable rules after
review; keep live failures and pending work in checkpoints, not in this reference.


Run `python <this-skill-directory>/scripts/test_disjoint_triage.py` after changing the governor-only terminal-triage exception; retain default triage ownership, same-title duplicate rejection, no-live-claim enforcement and other active workspace guards. Run `python <this-skill-directory>/scripts/test_source_freshness.py` for changed/appearing/deleted evidence, wrong workspace, symlink/path confinement and credential exclusions. Run `python <this-skill-directory>/scripts/test_engineering_signals.py` for bounded source leads, generated/symlink exclusion, root confinement and truthful budget truncation. Run `python <this-skill-directory>/scripts/test_discovery.py` for planning-vs-README ranking, broader engineering docs, upstream exclusions, and baseline/pruning fixtures. Run `python <this-skill-directory>/scripts/test_reconcile.py` for live terminal status overriding stale creation receipts without mutation. The bundled handoff regressions run with `python <this-skill-directory>/scripts/test_goal_handoff.py` and cover passive notification/readback, local-only preservation, visible subscription failures with durable card identity and prior-receipt preservation, cross-profile workspace ownership, active ownership, and same-title blocked-slice duplication. A title-only blocked check does not prove semantic deduplication: the picker must still compare source/objective, prior journal IDs, and unchanged prerequisites before handoff. Native subscriptions start at the current event cursor: if subscription registration races a terminal event, reconcile/report that result once through the next cron receipt rather than claiming history will replay. The bundled discovery helper is read-only and only finds candidate sources; manually verify their relevance and task state. Test it against fixture repositories with ROADMAP-only, nested TODO, absent queues, and pruned dependency directories. For a real run, selection must cite live project evidence and completion must cite executed checks. Skill installation is not proof of autonomous task completion.
