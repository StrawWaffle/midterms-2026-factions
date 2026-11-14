// Fingerprints of this build: one for the data, one for the site's own code.
// Pages carry them, /version.json publishes them, and the browser compares the
// two to tell a data update from a site update.
import { createHash } from 'node:crypto';
import { raw } from './data';
import { seats } from './analysis';

const hash = (text: string) => createHash('sha256').update(text).digest('hex').slice(0, 12);

// every source file of the site, read at build time
const sources = import.meta.glob('/src/**/*.{ts,astro,css}', { query: '?raw', import: 'default', eager: true }) as Record<string, string>;

export const VERSION = {
  data: hash(Object.keys(raw).sort().map((k) => k + '\n' + raw[k as keyof typeof raw]).join('\n')),
  code: hash(Object.keys(sources).sort().map((k) => k + '\n' + sources[k]).join('\n')),
  called: seats.filter((s) => s.called).length,
  seats: seats.length,
};
