// Proof-sheet generator — copy and adapt per surface.
//
// Purpose: judge a UI module's drawing at the size it actually ships, when the
// app's own data source cannot be reached from this host. It imports the REAL
// export the app calls and the REAL token sheet, so the sheet cannot flatter a
// hand-written approximation.
//
// Run it, screenshot the HTML it writes at 1x and 2x, then judge the 1x row
// first. The enlarged row only explains what the small one did.
//
// Edit the four CONFIG items, then: node templates/proof-sheet.mjs (or bun)

import { readFileSync, writeFileSync } from 'node:fs';

// ── CONFIG ──────────────────────────────────────────────────────────────────
// 1. The module and the export the app itself calls.
import { renderMark } from '/abs/path/to/the/module.ts';

// 2. A CSS file holding the app's token block. The whole `:root { ... }` block
//    is inlined, so the sheet draws in the app's own palette.
const TOKENS_FROM = '/abs/path/to/styles/global.css';

// 3. Every state the mark can take, including the ones that fail: each status
//    ink, each variant, the empty case, and the clamped extreme. The label is
//    what you will read next to the figure; keep it factual.
const CASES = [
	['default', { /* state fields */ }],
	['empty case', { /* … */ }],
	['clamped extreme', { /* … */ }]
];

// 4. Where to write the sheet.
const OUT = '/abs/path/to/scratch/proof-sheet.html';
// ────────────────────────────────────────────────────────────────────────────

const css = readFileSync(TOKENS_FROM, 'utf8');
const rootStart = css.indexOf(':root {');
const tokens = css.slice(rootStart, css.indexOf('}', rootStart) + 1);

// Each ground is one surface the mark is actually composited over. Add or drop
// rows to match the product, and never fall back to the page white.
const GROUNDS = [
	['on-surface-0', 'var(--color-surface-0)'],
	['on-surface-1', 'var(--color-surface-1)'],
	['on-surface-2', 'var(--color-surface-2)']
];

const figure = ([label, state]) =>
	`<figure><div class="stage">${renderMark(state)}</div><figcaption>${label}</figcaption></figure>`;

const row = (ground, cssVar) =>
	`<h2>${ground}</h2><div class="grid" style="--ground: ${cssVar}">${CASES.map(figure).join('')}</div>`;

writeFileSync(
	OUT,
	`<!doctype html><html lang="en"><head><meta charset="utf-8"><title>proof sheet</title><style>
${tokens}
body { font-family: system-ui, sans-serif; background: var(--color-surface-0); color: var(--color-text-primary); margin: 0; padding: 28px; }
.lede { color: var(--color-text-secondary); font-size: .8rem; max-width: 70ch; line-height: 1.6; }
h2 { font-size: .72rem; text-transform: uppercase; letter-spacing: .09em; color: var(--color-text-muted); margin: 26px 0 10px; }
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px 22px; }
figure { margin: 0; display: grid; gap: 8px; }
.stage { display: grid; place-items: center; min-height: 72px; background: var(--ground); border: 1px solid var(--color-border); border-radius: 8px; }
figcaption { color: var(--color-text-secondary); font-size: .68rem; line-height: 1.45; text-align: center; }
/* Paste the mark's own shipped styles here so the sheet cannot flatter it. */
</style></head><body>
<p class="lede">The real module over the app's real tokens, at the size it ships and enlarged. Judge the 1x row; the enlarged row only explains it.</p>
${GROUNDS.map(([g, v]) => row(g, v)).join('\n')}
</body></html>`
);

console.log('wrote', OUT);
