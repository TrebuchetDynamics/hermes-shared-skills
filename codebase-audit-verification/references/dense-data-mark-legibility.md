# Verifying a dense data mark at its shipping size

A compact mark that packs several readings into fixed slots — a map station glyph, a status dot, a table sparkline — fails in a way no unit test catches: it renders, its slots are all present, and at the size it actually ships the fine ones are an unreadable blur. Verify it as a drawing, by looking at it.

## Render the real renderer, not a mock

Import the module the product imports and emit its output. A proof sheet of the real markup over the product's real tokens settles legibility in one screenshot, where a hand-written SVG sample proves nothing about the shipped one.

## Judge at 1x first

The shipping size is the only size that matters, and an enlarged view will flatter a mark that fails small. Put both on one sheet, 1x first, then a magnified row for detail.

- A slot that cannot be read at 1x is **decoration**: move it out of the mark and into the tooltip and the accessible name rather than shipping a blur. It is worse than an absent slot, because a reader will try to decode it.
- Scale a clamped numeral by its own string length. A three-character clamp (`99+`) at the two-character font size overruns the ring it sits in.
- Weight a thin element so it separates from the outline it sits beside. A hairline arc against a ring of similar ink disappears at 1x; the stroke width is a legibility decision, not a detail.
- Give the mark an opaque backing fill so it reads over a busy field (map tiles, a photo, a gradient), and lift it with an offset-and-blur shadow rather than a zero-offset halo.

## Encode a state by shape when ink cannot carry it

Where the product requires that two provenance states never be confused, distinguish them by form as well as colour — filled against hollow — so the distinction survives greyscale and a colour-blind reader. A colour-only encoding is a defect the reviewer will catch and you should catch first.

## Draw the key from the same entries as the marks

A mark nobody can decode is decoration. Render the legend from the same slot definitions that draw the marks (one exported list), never by restating the shapes in prose — two sources drift, one cannot. That also gives the proof sheet its labels for free.

## Degrade by density, and recompute on every path that can change it

When the marks are plotted at scale, their fine slots collide as the view widens. Drop the fine slots below a threshold and keep the primary reading (the outline and its number), so zooming out degrades rather than smears.

Recompute the density on **every** path that can change the scale, not only the scale-change event: a refit that lands on the same scale fires no change event, so a density flag wired only to that event goes stale and the fine slots stay wrong until the reader happens to zoom. Keep the threshold in the module that owns the mark, so it has one tested source rather than a constant at the call site.

## The drawing carries no text to assistive technology

The mark is hidden from screen readers, so the plotted element's own label must restate every reading the drawing encodes — the count, the age, the provenance, the state. A glyph that is silent to a reader who cannot see it is an accessibility regression introduced by the drawing itself.

## State the boundary of what the sheet proves

A proof sheet validates the **mark**. It does not validate the integration: that the caller passes real data, that the legend renders, that the page builds. Say which of the two you established, and prefer the repo's own browser tooling for the integration check over an improvised one.
