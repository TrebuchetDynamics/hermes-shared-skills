# Guarding constant drift

Depth for the "guard it" step: deciding what can be guarded automatically, and proving the guard is neither noisy nor vacuous.

## Two guard shapes

1. **Dead-constant check** — every exported threshold is referenced somewhere outside its own file. Cheap, exact, zero false positives. Catches a *placebo knob*: a constant nothing reads, so tuning it changes nothing while appearing to.
2. **Collision check** — no threshold is re-hardcoded at a call site. This is the one that catches real drift, and the one that is easy to get wrong.

## Designing the collision check

Match on the literal's *value* only where coincidence is implausible, and only in positions where a threshold actually appears.

| Restriction | Why |
|---|---|
| decimal-valued constants only | integer thresholds collide constantly with unit conversions, `LIMIT`, and rounding |
| comparison operands only (`<= >= < >`, `BETWEEN`) | removes `percentile_cont(0.5)`, `Math.max(x, 0.01)` and similar argument-position coincidences |
| scan root = the detector tree | widening to the whole source tree reintroduces statistical coincidences |

Measured on a real tree: unfiltered value matching produced **963 candidates**, nearly all noise; the restricted form produced **0 false positives** over the detector tree and **34** when widened to all of `src`. The scan root is therefore a deliberate decision, not a default.

Known blind spots to state rather than chase: decimal thresholds used as a non-comparison argument (`COALESCE(col, 78.12)`), every integer-valued threshold, and a threshold re-expressed as arithmetic (`(x - 0.05) / 0.05` — a floor plus a width) rather than compared.

## Where the expected set comes from

Derive it from the source — parse the config file, grep the consumers — and never hand-type the list of names to check. A hand-maintained expectation list answers only "is what someone typed still present?", so it passes both a key the code reads but nobody documented and a documented key that nothing reads. That second case is the one to hunt deliberately: a documented name with no read site is a placebo knob a hand-listed check will never complain about.

## Proving the guard works

A guard reporting zero violations is indistinguishable from a guard examining nothing. Two mandatory checks:

1. **Discriminating power** — run the rule against the pre-change tree (`git show HEAD:<path>`) and confirm it flags the sites you just fixed. Record the count.
2. **Anti-vacuity assertion** — assert a minimum number of items scanned, so a refactor that changes the export shape fails loudly instead of silently passing.

Decisive optional check: temporarily reintroduce one violation, watch the guard fail with the expected location, then restore and compare the file against its pre-test content to prove byte-identical restoration.

## Scope honestly

A heuristic guard belongs only where its false-positive rate is zero. Where a value is an ordinary statistical number (`0.5`, `0.05` used for coverage, responsibility, ratio), the same value is a legitimate unrelated threshold — covering it needs an allowlist that rots. Keep the guard where it is exact, document the domains it does **not** cover, and say so rather than shipping a brittle one.

If the guard must live in a blocking gate (a deploy preflight), measure the false-positive rate first: a heuristic test that blocks shipping on a coincidence is worse than no test at all.

## Reporting a collision

Report the literal, the location, and the **candidate** constants — not a single asserted match. One literal can equal several constants' values, so the guard's job is to flag the collision for a human to resolve, not to guess which constant was meant.
