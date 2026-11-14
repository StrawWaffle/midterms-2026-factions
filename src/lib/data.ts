// Reads the four datasets in public/data at build time.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { csvParse } from 'd3';

export type Row = Record<string, string>;

const dir = resolve(process.cwd(), 'public/data');

export const FILES = ['house_2026.csv', 'statewide_2026.csv', 'senate_money_2026.csv', 'house_money_2026.csv'] as const;

export const raw: Record<(typeof FILES)[number], string> = Object.fromEntries(
  FILES.map((f) => [f, readFileSync(resolve(dir, f), 'utf-8')]),
) as Record<(typeof FILES)[number], string>;

const parse = (f: (typeof FILES)[number]) => csvParse(raw[f]) as unknown as Row[];

export const house = parse('house_2026.csv');
export const statewide = parse('statewide_2026.csv');
export const senateMoney = parse('senate_money_2026.csv');
export const houseMoney = parse('house_money_2026.csv');

/** Number or null for blank / non-numeric cells. */
export function num(v: string | undefined): number | null {
  if (v === undefined || v === null || v.trim() === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
