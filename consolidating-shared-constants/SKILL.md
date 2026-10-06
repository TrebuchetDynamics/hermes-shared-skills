---
name: consolidating-shared-constants
description: "Use when the same literal repeats across files."
version: 1.0.0
author: Hermes fleet agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [refactor, constants, thresholds, config-drift, guards, verification]
---

# Consolidating shared constants

Turning a literal that is hardcoded in several places into one named constant, wiring the sites, and guarding it so it cannot silently re-diverge.

## When to Use

A number or string appears in two or more places meaning the same thing; a config module claims to be the source of truth while code hardcodes the value; or the ask is "fix the duplicated thresholds" / "guard it".

## The decision rule

**Fix genuine duplication only.**

- Two or more sites with the same semantic = a defect, because they drift apart with no signal.
- A literal used once, in one module, is local detail. Centralising it buys indirection, not correctness.
- A **module-local named constant** for a threshold private to one module is a legitimate pattern, not a defect. Do not hoist it.

## Procedure

### 1. Enumerate every site — completely

Search by **value** as well as by identifier. Never treat a truncated sample as the list: if you printed the first N of M hits, you have N. Count the total, enumerate it in full, and only then declare a verified set.

A lowercase symbol grep misses camelCase stems — searching `gdop` will not find `preGdop` or `filteredGdop`. Grep the value, or use a case-insensitive stem.

### 2. Pair each site semantically, never by value

Several constants routinely share one value (in one config file, `20`, `3`, `2`, `50` and `300` each belonged to five to seven different exports). Value equality proves nothing about which constant belongs at which site. Read each site's surrounding expression and its column or operand, and match on meaning.

### 3. Choose the home by dependency layering

A constant needed by two layers must live in the **lower** one. Determine the direction empirically: check whether the lower layer imports the higher one.

- If the pure calculation layer never imports the server layer while the server layer imports the calculation layer, the shared constant belongs in the calculation layer.
- Never create a low-layer to high-layer import purely to share a constant.
- A file that is deliberately dependency-free (a generic executor module) is a signal to prefer its own module-local constant over an import.

### 4. Wire with the query builder's interpolation form

The same `${CONST}` syntax means different things per builder, and one of them can corrupt your parameters:

- **Tagged template (`sql`...``, drizzle)** — `${CONST}` binds a **parameter**; the SQL text changes (`>= 20` becomes `>= $1`). Confirm any query-shape test still passes.
- **Plain backtick string, `sql.raw(...)`, `client.unsafe(...)`** — `${CONST}` inlines the **literal**; the emitted SQL is byte-identical.
- **Positional-parameter APIs (`$1..$n` plus a params array)** — interpolate the constant as **text**. Adding it to the params array shifts every subsequent index.

### 5. Fix partial test mocks before running anything

A test that partially mocks the module you just extended returns `undefined` for the new export. Comparisons against `undefined` are silently `false`, so behaviour changes and the failure looks unrelated to your edit.

Prefer spreading the real module so the mock cannot drift again:

```ts
vi.mock('$lib/thing', async (importOriginal) => ({
  ...(await importOriginal<typeof import('$lib/thing')>()),
  overriddenFn: vi.fn(() => 42),
}));
```

Grep the test tree for mocks of every module whose exports you added.

The mirror image is a fake that is too **broad**. When you stub a low-level call that the function under test makes for more than one purpose — a `git` probe and the real `docker` invocation, say — a single blanket fake answers both, feeding the first call's canned stdout into the second, and the test then passes for the wrong reason. Dispatch the fake on `argv[0]` and assert which commands were actually issued.

### 6. Verify centrally

Run the **full** suite, not just the touched subtree — a constant can be consumed far from where it is declared, and the calculation layer is usually the most heavily tested. Add the typecheck.

When fanning the wiring out to subagents: give each a **disjoint file set**, and forbid them from running the shared suite concurrently (each would see its siblings' half-applied edits). Verify their diffs against your own site map — a child can edit its own file correctly and still miss a sibling site in another file.

### 7. Guard it

A guard is only worth shipping if it is exact and non-vacuous. See `references/guarding-constant-drift.md` for the two guard shapes, the predicate that keeps false positives at zero, and how to prove discriminating power.

## Pitfalls

- **Truncated output is not a complete list.** Declaring a set "hand-verified" from a truncated sample under-counts silently. Count first, then enumerate.
- **A value-matching guard over integer thresholds is noise.** Unit conversions (`x * 1000`), `LIMIT`, and rounding (`Math.round(x * 10) / 10`) collide with almost every small integer. Restrict to decimals and comparison operands.
- **A guard reporting zero violations may be examining nothing.** Prove it fires against the pre-change tree, and assert a minimum number of items scanned.
- **Widening a guard's scan root is a measurement, not a preference.** Widen only while the false-positive rate stays at zero.
- **Changing an operator is a behaviour change even when the argument is a constant.** `<` and `<=` at the same threshold disagree exactly on the boundary. Call that out explicitly rather than folding it into a "no behaviour change" edit.
- **Re-run the suite after fixing mocks.** The first green run after a partial-mock fix can still hide a second mock in a file you did not open.
- **A literal that is the *span* between two thresholds is derived, not a copy.** `(x - 0.05) / 0.05` encodes a floor *and* a width; wire it as `(x - LO) / (HI - LO)`, or the width survives as a hardcoded second copy that silently diverges when a threshold moves. It is arithmetic, not a predicate, so a comparison-operand guard will never flag it — find these by reading expressions, not by scanning for comparison operators.
- **A guard whose expected set is hand-typed cannot detect divergence.** When the guard lists the names it checks, it proves only that entries someone once typed still exist — it is blind in *both* directions, to a key the code reads and nobody documented and to a documented key nothing reads. Derive the expected set from the source and assert the derived set is satisfied.
- **A declared name is not a read name.** A documented config key, an exported constant, or a doc-claimed default with no read site is a placebo: changing it does nothing while looking authoritative. Grep for the consumer (excluding tests) before trusting the declaration — and watch for a near-miss pair, the docs naming `PREFIX_THING` while the code reads only the legacy `THING` spelling, which passes every hand-listed check.
