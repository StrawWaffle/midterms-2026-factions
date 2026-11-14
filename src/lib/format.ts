// Number formatting with a true minus sign.
export const signed = (v: number, digits = 1) => {
  const s = Math.abs(v).toFixed(digits);
  return Number(s) === 0 ? s : (v < 0 ? '−' : '+') + s;
};
export const fixed = (v: number, digits = 1) => (v < 0 ? '−' : '') + Math.abs(v).toFixed(digits);
export const usd = (v: number, digits = 2) => '$' + v.toFixed(digits);
export const millions = (v: number) => '$' + (v / 1e6).toFixed(1) + 'M';
export const interval = (lo: number, hi: number, digits = 1) => `${signed(lo, digits)} to ${signed(hi, digits)}`;
export const pct = (v: number) => `${Math.round(v)}%`;

/** Small deterministic jitter in [-spread, spread] from a string key. */
export function jitter(key: string, spread: number) {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619);
  return (((h >>> 0) / 0xffffffff) - 0.5) * 2 * spread;
}
