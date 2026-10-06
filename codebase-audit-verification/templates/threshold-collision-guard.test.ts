/*
 * Threshold collision guard — fails when a decimal-valued threshold constant is
 * re-hardcoded as a comparison operand in a consumer.
 *
 * This is the second half of the placebo-knob problem: a constant can be
 * imported at one site while the same value stays hardcoded in a sibling, so
 * the two drift apart silently and no reference-count can see it.
 *
 * WHY DECIMALS ONLY, and why the scan is scoped — both measured, not assumed:
 *  - integer thresholds collide constantly (1, 2, 3, 5, 10, 20, 50, 100, 300
 *    appear as unit conversions, LIMIT clauses, rounding idioms). A
 *    value-matching guard over them produced ~960 candidates, nearly all
 *    noise. That predicate was REJECTED; do not reintroduce it.
 *  - decimals are near-impossible to hit by coincidence, and restricting to
 *    COMPARISON contexts removes the rest (`percentile_cont(0.5)`,
 *    `Math.max(x, 0.01)`).
 *  - scope must be measured: the detector subtree scored 0 false positives
 *    while the whole source tree scored dozens from unrelated modules. Run the
 *    predicate at each candidate scope and keep the one that measures clean.
 *
 * ADAPT: CONFIG_FILE / SCAN_ROOT / the export regex / the decimal filter.
 * Keep the non-vacuity floor and the candidate-style output message.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const HERE = fileURLToPath(new URL('.', import.meta.url));
/** the file declaring the thresholds */
const CONFIG_FILE = join(HERE, '<path-to>/thresholds/config.ts');
/** the subtree the collision scan covers — chosen by measurement, see header */
const SCAN_ROOT = join(HERE, '..');
/** only for reporting paths relative to the repo source root */
const REPORT_ROOT = join(HERE, '..', '..', '..', '..');

function walk(dir: string, out: string[] = []): string[] {
	for (const entry of readdirSync(dir, { withFileTypes: true })) {
		const full = join(dir, entry.name);
		if (entry.isDirectory()) {
			if (entry.name !== 'node_modules') walk(full, out);
		} else if (entry.name.endsWith('.ts')) {
			out.push(full);
		}
	}
	return out;
}

describe('threshold config', () => {
	it('no decimal threshold constant is re-hardcoded as a comparison operand', () => {
		const configSource = readFileSync(CONFIG_FILE, 'utf8');
		const decimals = [...configSource.matchAll(/^export const ([A-Z0-9_]+)\s*=\s*(-?\d+\.\d+);/gm)].map(
			(m) => ({ name: m[1], value: m[2] })
		);

		// Non-vacuity floor: if the export shape changes, fail loudly instead of
		// passing forever with nothing to check.
		expect(decimals.length).toBeGreaterThanOrEqual(8);

		const offenders = new Set<string>();
		for (const file of walk(SCAN_ROOT)) {
			if (file.endsWith('.test.ts') || file === CONFIG_FILE) continue;
			const rel = relative(REPORT_ROOT, file);
			const lines = readFileSync(file, 'utf8').split('\n');
			for (const [i, raw] of lines.entries()) {
				const line = raw.trim();
				if (line.startsWith('*') || line.startsWith('//')) continue; // prose mentions are fine
				for (const { name, value } of decimals) {
					const v = value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
					// comparison contexts only — the filter that removed the noise class
					const asOperand = new RegExp(`(<=|>=|<|>)\\s*${v}(?![0-9.])|(?<![0-9.])${v}\\s*(<=|>=|<|>)`);
					if (asOperand.test(line)) {
						// Report candidates, never a resolution: several constants can
						// legitimately share one value.
						offenders.add(`${rel}:${i + 1}  [${name} = ${value}]  ${line}`);
					}
				}
			}
		}

		expect(
			[...offenders],
			`A decimal threshold is hardcoded as a comparison operand. Import the constant at the site,\n` +
				`or give the literal a named local constant if it is a different threshold that merely\n` +
				`shares the value:\n` +
				[...offenders].join('\n')
		).toEqual([]);
	});
});
