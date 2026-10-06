# Native workflow harnesses

Use when validating a cross-process desktop journey, launcher ownership or exact
session recovery beyond the first inventory page.

## Establish a meaningful restoration scenario

1. Trace the production directory/channel reads and the fixture's inventory,
   metadata and canonical-history routes. Choose an exact profile/session tuple;
   preserve authoritative identity rather than creating a replacement session.
2. Put the remembered session genuinely on a later page. Independently enforce
   a small server page cap, return a different session on offset zero with
   `has_more=true`, and return the remembered session on the next offset. Merely
   hiding the target everywhere does not test pagination or discoverability.
3. Probe both pages and exact metadata/history before launching Flutter. Request
   the normal client limit as well as the fixture cap, because a larger request
   must not accidentally pull the target back onto page one.
4. Persist the tuple in one app process, relaunch a second against the same owned
   preferences and fixture, and assert new-process exact metadata/history reads.
   Compare submission, creation, approval and Stop counters across recovery;
   inventory identity alone cannot prove that no mutation was replayed.
5. Keep model-selection fixtures separate if the lifecycle contract forbids model
   writes. Report separate scenario coverage explicitly; do not call it one
   integrated model/generation journey.

## Supervise and cancel owned work

1. Give the launcher a marked isolated HOME/XDG root and an owned display. Preserve
   logs outside the root; remove only roots that satisfy marker and containment
   checks. Keep installed SDK/package caches explicit rather than reinstalling.
2. Start the bounded runner asynchronously in a fresh process session, for example
   `setsid timeout --signal=TERM --kill-after=15s 600s ... &`; capture its PID and
   use Bash `wait`. Do not put the long runner directly in the foreground under
   an exit-only TERM trap: Bash defers that trap until the external command ends.
3. Forward launcher TERM/INT to its owned process group, wait for teardown, check
   remaining non-zombie group members and escalate within a bounded deadline.
   Remove isolated state only after owned work is gone; retain it and report a
   blocker if cleanup cannot prove that condition.
4. Track children started in separate sessions as separate process groups. Signal
   all owned groups first, use one shared grace deadline, escalate and reap them;
   waiting for one leader does not prove its descendants terminated.
5. Make signal cleanup idempotent. Ignore repeated termination signals while
   unwinding so timeout/group forwarding cannot interrupt cleanup before its
   receipt is written.
6. Exercise harmless extracted-source probes before expensive native execution:
   signal only the launcher PID with TERM and INT, add a child that genuinely
   ignores TERM, send repeated TERM, and assert expected exits, bounded completion,
   no owned survivors, and state removal only after cleanup. These are supervisor
   proofs, not evidence of GTK/plugin behavior.

## Own fixture startup and failure paths

- Wait for the exact spawned child's bind announcements before sending requests;
  port reservation followed by release still has a bind race, so fail closed.
- Keep wrapper backends on fixed owned loopback ports with bounded responses and
  receipts. Preserve exact metadata/history from the authoritative fixture while
  changing only the synthetic inventory projection needed by the scenario.
- Probe public-port collision, backend death, oversized responses and receipt
  exhaustion. Assert owned listeners/children close while an independently owned
  conflicting listener remains untouched; successful startup tests do not cover
  partial-startup cleanup.
- Keep fixture source/probe checks, unit suites and actual two-process native
  execution as separate evidence. A preflight refusal proves refusal, not the
  journey behind it. Recheck prerequisites when the environment changes rather
  than recording missing packages as a permanent limitation.
