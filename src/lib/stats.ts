// Ordinary least squares with classical or HC1 (heteroskedasticity-robust) standard errors,
// matching statsmodels' `cov_type="HC1"`. Small dense matrices only.

type Matrix = number[][];

function invert(a: Matrix): Matrix {
  const n = a.length;
  const m = a.map((row, i) => [...row, ...row.map((_, j) => (i === j ? 1 : 0))]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(m[r][c]) > Math.abs(m[p][c])) p = r;
    [m[c], m[p]] = [m[p], m[c]];
    const pv = m[c][c];
    if (Math.abs(pv) < 1e-12) throw new Error('singular design matrix');
    m[c] = m[c].map((v) => v / pv);
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = m[r][c];
      m[r] = m[r].map((v, j) => v - f * m[c][j]);
    }
  }
  return m.map((row) => row.slice(n));
}

export interface Fit {
  names: string[];
  beta: number[];
  cov: Matrix;
  n: number;
  k: number;
  r2: number;
}

/** y = X b + e. `X` rows must already contain the intercept column if one is wanted. */
export function ols(y: number[], X: Matrix, names: string[], robust: 'HC1' | 'classical'): Fit {
  const n = y.length, k = X[0].length;
  const XtX: Matrix = Array.from({ length: k }, (_, a) => Array.from({ length: k }, (_, b) => {
    let s = 0;
    for (let i = 0; i < n; i++) s += X[i][a] * X[i][b];
    return s;
  }));
  const inv = invert(XtX);
  const Xty = Array.from({ length: k }, (_, a) => {
    let s = 0;
    for (let i = 0; i < n; i++) s += X[i][a] * y[i];
    return s;
  });
  const beta = inv.map((row) => row.reduce((s, v, j) => s + v * Xty[j], 0));
  const res = y.map((v, i) => v - X[i].reduce((s, x, j) => s + x * beta[j], 0));
  const ybar = y.reduce((s, v) => s + v, 0) / n;
  const r2 = 1 - res.reduce((s, e) => s + e * e, 0) / y.reduce((s, v) => s + (v - ybar) ** 2, 0);
  let cov: Matrix;
  if (robust === 'classical') {
    const s2 = res.reduce((s, e) => s + e * e, 0) / (n - k);
    cov = inv.map((row) => row.map((v) => v * s2));
  } else {
    // HC1: (X'X)^-1 X' diag(e^2) X (X'X)^-1 * n/(n-k)
    const meat: Matrix = Array.from({ length: k }, (_, a) => Array.from({ length: k }, (_, b) => {
      let s = 0;
      for (let i = 0; i < n; i++) s += X[i][a] * X[i][b] * res[i] * res[i];
      return s;
    }));
    const scale = n / (n - k);
    const left = inv.map((row) => Array.from({ length: k }, (_, b) => row.reduce((s, v, j) => s + v * meat[j][b], 0)));
    cov = left.map((row) => Array.from({ length: k }, (_, b) => row.reduce((s, v, j) => s + v * inv[j][b], 0) * scale));
  }
  return { names, beta, cov, n, k, r2 };
}

export interface Estimate { est: number; se: number; lo: number; hi: number; p: number; n: number }

// two-sided p-value from a normal approximation, as statsmodels reports with robust covariance
function normalP(z: number) {
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989423 * Math.exp((-z * z) / 2);
  const tail = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return 2 * tail;
}

/** Linear combination of coefficients, e.g. {mod_only: 1, prog_only: -1}. 95% interval, normal approximation. */
export function contrast(fit: Fit, weights: Record<string, number>): Estimate {
  const w = fit.names.map((nm) => weights[nm] ?? 0);
  const est = w.reduce((s, v, i) => s + v * fit.beta[i], 0);
  let varr = 0;
  for (let a = 0; a < w.length; a++) for (let b = 0; b < w.length; b++) varr += w[a] * w[b] * fit.cov[a][b];
  const se = Math.sqrt(varr);
  return { est, se, lo: est - 1.96 * se, hi: est + 1.96 * se, p: normalP(est / se), n: fit.n };
}

export function mean(xs: number[]) {
  return xs.reduce((s, v) => s + v, 0) / xs.length;
}

/** Mean with a 95% interval (normal approximation, sample standard deviation). */
export function meanCI(xs: number[]) {
  const m = mean(xs);
  const sd = Math.sqrt(xs.reduce((s, v) => s + (v - m) ** 2, 0) / (xs.length - 1));
  const se = sd / Math.sqrt(xs.length);
  return { mean: m, lo: m - 1.96 * se, hi: m + 1.96 * se, n: xs.length };
}
