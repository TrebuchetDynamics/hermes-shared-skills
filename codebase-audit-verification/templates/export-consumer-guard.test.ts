import { readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

/**
 * Guard: every exported tunable in CONFIG_FILE must be referenced somewhere
 * outside that file.
 *
 * A constant with zero consumers is a *placebo knob*: the consumer hardcodes
 * its own literal, so tuning the constant changes nothing. That divergence is
 * invisible until someone tunes a threshold and the behaviour does not move.
 *
 * NOT SUFFICIENT ON ITS OWN. This catches only zero-reference constants. It
 * cannot see a constant imported at one site while the same value stays
 * hardcoded as a literal in sibling consumers. Pair a constant to a site by
 * reading the consumer, never by matching the value — values collide across a
 * dozen tunables, so a value-matched import is a silent behaviour change.
 *
 * Prove it discriminates: point CONFIG_FILE at the pre-fix revision and
 * confirm it fails, then at the current revision and confirm it passes. A
 * guard that has never been seen to fail is not a guard.
 *
 * Runs without a database or network. Copy and adjust the three constants
 * below; keep the comment — the next reader needs the blind spot.
 */

// --- adjust these -------------------------------------------------------
/** The single-source-of-truth config module to police. */
const CONFIG_FILE = join(fileURLToPath(new URL('.', import.meta.url)), 'config.ts');
/** Tree to scan for consumers; must contain CONFIG_FILE. */
const SRC_ROOT = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..');
/** CONFIG_FILE's path relative to SRC_ROOT (excluded from the consumer set). */
const SELF = 'lib/config.ts';
// -----------------------------------------------------------------------

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

describe('config has no placebo knobs', () => {
	it('exports no constant that nothing consumes', () => {
		const configSource = readFileSync(CONFIG_FILE, 'utf8');
		const exported = [...configSource.matchAll(/^export const ([A-Z0-9_]+)/gm)].map((m) => m[1]);

		// A zero-export read means the regex or the path is wrong, not that the
		// file is clean — fail loudly rather than passing vacuously.
		expect(exported.length).toBeGreaterThan(0);

		const otherSources = walk(SRC_ROOT)
			.filter((p) => relative(SRC_ROOT, p) !== SELF)
			.map((p) => readFileSync(p, 'utf8'))
			.join('\n');

		const unreferenced = exported.filter((name) => !new RegExp(`\\b${name}\\b`).test(otherSources));

		expect(
			unreferenced,
			`Unreferenced tunable(s) — import each at its consumer's site or delete it; ` +
				`a threshold nothing reads cannot tune anything:\n` +
				unreferenced.join('\n')
		).toEqual([]);
	});
});
