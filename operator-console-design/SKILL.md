---
name: operator-console-design
description: "Use when designing or verifying an operator console UI."
version: 1.0.0
author: Hermes fleet agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [design, ui, frontend, verification, console, dashboard]
---

# Designing and verifying an operator console

Operator-facing consoles (fleet registers, catch ledgers, dashboards) are judged on whether a technician can read the state of many things at once, not on whether the page is attractive. This skill covers choosing a direction that survives the owner's review, executing it instead of asking, and proving the result when the console's own data source is out of reach.

For the full design workflow — mode selection, init, direction rounds, craft floor — defer to the `impeccable` skill. This carries only the lessons that decide whether the work lands.

## When to Use

Load when asked to design, redesign, extend, or visually verify an operator-facing console: a fleet register, catch ledger, device dashboard, settings panel, or any surface a technician reads state from under time pressure. Also load when an existing console needs its reading clarity improved, when a design direction must survive owner review, or when a UI change needs visual proof and the console's own data source is unreachable from the development host.

## Choosing a direction

1. **Ground every candidate in the product's job, not its culture.** A direction is chosen by what it makes *readable*, so each candidate must be able to name what it renders about the actual job. For a tool whose job is fleet position and capture, candidates carrying neither geography nor telemetry are wrong however attractive, and the owner will reject the whole analysis rather than the taste. Derive from the audience's graphic traditions, not from its decorative materials.
2. **Bounded contribution: type, palette, density, one signature move.** A world supplies those and nothing more. Layout, navigation and controls stay the platform's own, because a working screen has to keep behaving like one. A direction that reorganises the shell has overreached.
3. **Pick one signature move and make it earn the goal.** The move should answer the question the operator actually has (where are my rigs, what have they caught) rather than decorate it. One move, decodable from a key rendered from the same source that draws it.
4. **Execute the recommended direction; do not close a pass by asking the owner to pick.** A visual direction is reversible, so build the recommended one and report the alternatives as a one-line questionnaire with the built default standing. Ending on "the build starts when you pick" stalls work the owner expected to see.

## Verifying without the app's data

When the console's database or service is unreachable from the development host, the page cannot be rendered end to end. Verify the artifact instead of claiming the page.

1. **Render the real module, not a copy.** Import the exact export the app calls and emit its markup into a standalone HTML page against the app's real token block (read the token sheet from source). A hand-copied approximation verifies nothing, because it cannot drift the way the real one can.
2. **Sweep the states that can fail, at the size they ship.** One figure per state — each status ink, each freshness/aging variant, the empty case, the clamped extreme — at 1× and then enlarged, over every ground the mark actually lands on.
3. **Judge 1× first.** The shipping size is the one that matters; the enlarged view only explains what the small one did.
4. **State the page-level render as unverified, with the reason.** "The component renders; the page does not, because the data source refuses this host" is a complete and honest result. Never let a proof sheet stand in for a page render, and never dress up an unreached render as verified.

A generator to copy and adapt: `templates/proof-sheet.mjs`.

## Pitfalls

- **A reading that is illegible at the size it ships is worse than an absent one.** A label that renders as a blur at the real size is noise the operator has to ignore; move it to the hover/popup and the accessible name, and spend the pixels on what reads. Judge this from the 1× capture, not from the enlarged one.
- **Re-test extreme values at the real size.** A clamped or widened value changes how much space it needs — a value clamped upward overflowed its container until its font size scaled with its length. Every clamp needs its own look at 1×.
- **A mark must carry its meaning without colour.** Filled versus hollow, solid versus dashed — a state distinguished by hue alone disappears in greyscale and for colour-blind operators, and it is also the state a screen reader cannot recover. Give the drawing an accessible name that restates every slot.
- **Prove the changed module still behaves, not just that it compiles.** A type check and a build prove the page assembles. The behavioural check is the module's own test suite plus the rendered judgement above, and the two answer different questions — report them separately.
- **Capture a locally-served page with a local browser.** A remote browser harness resolves `localhost` to its own machine, so a dev server on this host is unreachable from it; drive the repo's own browser tooling (its Playwright, if the repo has one) for localhost captures. Where the expected browser revision is absent, either let that tool install it or point it at an already-installed browser binary; and note that a dev server may bind `localhost` over IPv6 while `127.0.0.1` refuses.
- **Separate what you ran from what you did not.** Static checks, unit suites, production builds, and rendered judgement are four different kinds of evidence. Reuse a recorded result only for bytes proven unchanged; otherwise re-run, and say plainly which checks were not run.

## Boundaries

- **Do not redeploy, restart, or migrate to see a screen.** A render is not worth an operation; if the only path to a page render is a production action, report the gap instead.
- **Serve captures from a fixture or a snapshot, never a data write.** A verification pass reads; it does not seed, backfill, or annotate to make a screenshot possible.
- **The product record wins.** Where a design contradicts an accepted product decision or a rule the code already enforces, the record and the code are right.
