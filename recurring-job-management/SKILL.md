---
name: recurring-job-management
description: "Use when tuning a Hermes cron job's schedule or cadence."
version: 1.0.0
author: Hermes fleet agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [cron, scheduling, jobs, cadence, automation]
---

# Managing recurring jobs

Changing a recurring job's cadence looks like editing one string. It is the place a
change silently fails to take, or silently quadruples a run budget.

## When to use

Load when changing a scheduled job's frequency, time, or delivery, when adding or
retiring one, or when checking why one did not fire. The schedule is this skill's
subject; what the job *does* belongs to the skill the job runs.

## Where the jobs live

The active profile owns its jobs at `~/.hermes/profiles/<profile>/cron/jobs.json`;
the default profile keeps a separate set under `~/.hermes/cron/`. **A profile only
owns its own jobs** — never read-modify-write another profile's file, even when the
job you were asked about looks similar.

## Changing the cadence

1. **Read the job first.** Capture the whole current record — identifier,
expression, `next_run_at`, delivery target, pinned model, continuity, skills,
workdir. Step 4 compares against this.
2. **Design the expression to preserve the existing ticks.** When a job sits at a
deliberately off-the-hour offset, do not switch it to `*/N`: that moves it onto the
top of the hour and discards an offset someone chose. Add the complementary minutes
to the same list, and check the arithmetic all the way round the hour, including the
wrap from the last minute to the first:

   | Cadence | Expression |
   |---|---|
   | hourly at :43 | `43 * * * *` |
   | 30-min | `13,43 * * * *` |
   | 15-min | `13,28,43,58 * * * *` |

   Every consecutive pair, and `58 -> 13`, differ by exactly the intended interval.
   Prefer an explicit minute list over a step range (`13-58/15`): the expanded set is
   what actually fires, and a range's endpoints misread easily.
3. **Change only the field you mean to change.** Pass the job identifier and the new
schedule; omitting the other fields leaves delivery target, pin, continuity, skills
and workdir as they were.
4. **Verify by read-back, never by the update response.** A success response means
only that the write was accepted. Read the on-disk job entry *and* the CLI listing,
confirm the expression, and confirm `next_run_at` is genuinely the next tick relative
to the current clock (`date`). A `next_run_at` already in the past — or one still
showing the old cadence — means the change did not take.

## Scheduling a one-shot for a future deadline

When an accepted decision needs an action at a time you cannot reach in-session — a
measurement window closing, an RF gap opening, a maintenance slot — create a one-shot
job instead of waiting, polling, or leaving it to "the next pass", which is a hope and
not a mechanism. Two things make it safe:

- **Make the prompt re-verify its own precondition and fail closed.** A time-gated
action's premise can be false when it actually fires: the window may not have closed,
the restart may still be forbidden, the work may already have been done. The job must
check the condition first and stop with a report when it does not hold, rather than
taking a destructive step on a stale assumption. The scheduler guarantees *when*, never
*that the world still matches* — so the brief has to carry the check itself.
- **Confirm `next_run_at` sits on the correct side of the deadline.** Read it back
against `date -u`: deadlines are usually stated in UTC while the job record carries a
local offset, and a job that fires *before* the window closes does the opposite of what
was asked. The creation response says nothing about that.

## Report the consequence, not just the new expression

- **State the multiplier.** Doubling the cadence doubles the run count and, for a job
that spends model tokens, roughly doubles the spend. "Four runs an hour instead of
one" is the fact the owner is buying.
- **Say why a higher cadence is tolerable when it is.** A job whose contract includes
a silent no-op protocol (report nothing when there is no eligible work) is what keeps
a high frequency informative rather than noisy. That is the reason to give — not a
blanket assurance that it will be fine.
- **A cadence change leaves the job's name stale.** A job named `...-hourly` that now
runs four times an hour is wrong in every listing. Flag it and offer the rename; do
not rename it silently, and do not leave it unmentioned.
- Retired one-shot jobs often remain in the listing, disabled. Name them when you
report, so the owner can clear them.

## Ownership rules

- **A recurring job must never reschedule itself.** An autonomous run that edits its
own cadence turns a bounded frequency into an unbounded one with no owner decision
in the loop. Schedule and frequency changes are owner actions: apply them when asked,
and never let a job's own run apply one.
- **Tuning a job's schedule is a different permission from editing the skill the job
runs.** A shared, hub-installed, or user-owned skill can forbid a project profile
from editing it while that profile still owns the schedule. Establish which of the
 two you are being asked to change before writing anything.

## Pitfalls

- Cron fields are five-position and evaluated in the host's local time; job records
carry an offset. Compare `next_run_at` against `date` in that same offset rather than
against a UTC reading.
- Do not verify a schedule change by waiting for the next fire, or by polling or
sleeping on it. The state file and the listing answer it immediately.
- A state change confirmed only by the tool that made it is not confirmed. Read the
artifact the scheduler itself will read.
