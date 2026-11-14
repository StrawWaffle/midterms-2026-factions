// Every number on the page that comes from this site's own datasets is computed here, at build
// time, so the prose and charts stay in step when the data is updated.
import { house, statewide, senateMoney, houseMoney, num, type Row } from './data';
import { ols, contrast, mean, meanCI, type Estimate } from './stats';
import { HOUSE_ROWS, type Faction } from './factions';
import { median } from 'd3';

// ------------------------------------------------------------------ House

export interface Seat {
  code: string; dem: string; rep: string; faction: Faction;
  margin: number; pres24: number; overperf: number;
  dInc: boolean; rInc: boolean; incumbency: string;
  prog: boolean; mod: boolean; progStrict: boolean; modStrict: boolean;
  hisp: number | null; ba: number | null;
  priorParty: string; winner: string; called: boolean; pctCounted: number | null;
}

// AK-AL is left out: the Republican's main opponent there was an independent, Bill Hill, whom the
// DCCC put on Red to Blue; the Democratic nominee took under 8 percent.
export const HOUSE_EXCLUDE = new Set(['AK-AL']);

export const seats: Seat[] = house.filter((r) => !HOUSE_EXCLUDE.has(r.code)).map((r) => ({
  code: r.code, dem: r.dem_nominee, rep: r.rep_nominee, faction: r.faction as Faction,
  margin: num(r.dem_margin)!, pres24: num(r.pres24_margin)!, overperf: num(r.overperf)!,
  dInc: r.d_inc === '1', rInc: r.r_inc === '1', incumbency: r.incumbency,
  prog: r.prog === '1', mod: r.mod === '1', progStrict: r.prog_strict === '1', modStrict: r.mod_strict === '1',
  hisp: num(r.hisp_share_acs24), ba: num(r.ba_plus_share_acs24),
  priorParty: r.prior_party, winner: r.winner_party, called: r.called === '1', pctCounted: num(r.pct_expected_vote),
}));

export const competitive = (s: Seat) => Math.abs(s.pres24) <= 15;
export const OUTLIERS = ['TX-15', 'TX-28', 'TX-34', 'TX-35', 'CA-13', 'CA-21', 'CA-22']; // South Texas and Central Valley

const byFaction = (f: Faction) => seats.filter((s) => s.faction === f);

export const houseGroups = HOUSE_ROWS.map((f) => {
  const rows = byFaction(f);
  const over = rows.map((s) => s.overperf);
  const pres = rows.map((s) => s.pres24);
  return {
    faction: f, n: rows.length,
    over: meanCI(over), overMedian: median(over)!,
    presMedian: median(pres)!, nCompetitive: rows.filter(competitive).length, nTrump: pres.filter((p) => p < 0).length,
  };
});
export const group = (f: Faction) => houseGroups.find((g) => g.faction === f)!;

export const houseMeanAll = mean(seats.map((s) => s.overperf));
export const houseMeanCompetitive = mean(seats.filter(competitive).map((s) => s.overperf));
export const nCompetitive = seats.filter(competitive).length;

// A flip is a Republican-held seat the Democrat won, or leads while the race is still uncalled.
const demAhead = (s: Seat) => s.winner === 'D' || (!s.winner && s.margin > 0);
const repAhead = (s: Seat) => s.winner === 'R' || (!s.winner && s.margin < 0);
export const flips = seats.filter((s) => s.priorParty === 'R' && demAhead(s)).sort((a, b) => a.margin - b.margin);
export const flipsUncalled = flips.filter((s) => !s.winner);
export const flipCount = (f: Faction) => flips.filter((s) => s.faction === f).length;
export const flipsUnder = (pts: number, fs?: Faction[]) => flips.filter((s) => s.margin < pts && (!fs || fs.includes(s.faction))).length;
export const flipsBy = (fs: Faction[]) => flips.filter((s) => fs.includes(s.faction)).length;
export const lostClose = seats.filter((s) => repAhead(s) && s.margin > -3);
export const uncounted = seats.filter((s) => s.pctCounted !== null && s.pctCounted < 95).length;
export const uncalled = seats.filter((s) => !s.called).length;
export const seatByCode = (code: string) => seats.find((s) => s.code === code)!;

// Regressions: Democratic margin on 2024 margin, incumbency and faction flags (HC1 robust errors).
function houseFit(rows: Seat[], strict: boolean, controls = false) {
  const names = ['const', 'pres24', 'd_inc', 'r_inc', 'prog_only', 'mod_only', 'both', ...(controls ? ['hisp', 'ba'] : [])];
  const X = rows.map((s) => {
    const p = strict ? s.progStrict : s.prog, m = strict ? s.modStrict : s.mod;
    return [1, s.pres24, +s.dInc, +s.rInc, +(p && !m), +(m && !p), +(p && m), ...(controls ? [s.hisp!, s.ba!] : [])];
  });
  return ols(rows.map((s) => s.margin), X, names, 'HC1');
}
const modMinusProg = (fit: ReturnType<typeof houseFit>) => contrast(fit, { mod_only: 1, prog_only: -1 });

export const houseModels = {
  broadAll: modMinusProg(houseFit(seats, false)),
  broadCompetitive: modMinusProg(houseFit(seats.filter(competitive), false)),
  strictAll: modMinusProg(houseFit(seats, true)),
  strictNoOutliers: modMinusProg(houseFit(seats.filter((s) => !OUTLIERS.includes(s.code)), true)),
  strictControls: modMinusProg(houseFit(seats.filter((s) => s.hisp !== null && s.ba !== null), true, true)),
};
export const nStrictProg = seats.filter((s) => s.progStrict && !s.modStrict).length;
export const nStrictMod = seats.filter((s) => s.modStrict && !s.progStrict).length;

// ------------------------------------------------------------------ Senate and governor

const OFF = (o: string) => (o.startsWith('Senate') ? 'Senate' : 'Governor');
const EXCLUDE = new Set(['RI|Governor', 'WY|Governor', 'MT|Senate']); // Democrat not one of the top two

export interface Race {
  key: string; st: string; state: string; office: 'Senate' | 'Governor'; dem: string; faction: Faction;
  margin: number; pres24: number; swing: number; demPct: number;
  dInc: boolean; rInc: boolean; cook: number | null; white: number | null; oppWeak: number | null; repOfficeholder: number | null;
  lowConfidence: boolean;
}

export const races: Race[] = statewide
  .filter((r) => r.dem_type === 'Democrat' && !EXCLUDE.has(`${r.st}|${OFF(r.office)}`))
  .map((r) => ({
    key: `${r.st}-${OFF(r.office)}`, st: r.st, state: r.state, office: OFF(r.office), dem: r.dem_nominee,
    faction: (r.faction || 'mixed-unclear') as Faction,
    margin: num(r.dem_margin)!, pres24: num(r.pres2024_margin)!, swing: num(r.swing_vs_2024)!, demPct: num(r.dem_pct)!,
    dInc: r.dem_incumbent === 'True', rInc: r.rep_incumbent === 'True', cook: num(r.cook_num),
    white: num(r.white_share_pct), oppWeak: num(r.opp_weak_flag), repOfficeholder: num(r.rep_officeholder),
    lowConfidence: r.faction_confidence === 'low',
  }));

export const raceByKey = (k: string) => races.find((r) => r.key === k)!;

// Average relationship between 2024 margin and swing (simple OLS slope). Vermont's governor race
// is left out of the fit: the Democrat ran against Phil Scott, a popular Republican incumbent, so
// its swing from the presidential result says little about the state's mood.
export const SLOPE_EXCLUDE = ['VT-Governor'];
const slopeFit = (rs: Race[]) => ols(rs.map((r) => r.swing), rs.map((r) => [1, r.pres24]), ['const', 'pres24'], 'classical');
export const swingSlope = (() => {
  const fit = slopeFit(races.filter((r) => !SLOPE_EXCLUDE.includes(r.key)));
  return { slope: fit.beta[1], intercept: fit.beta[0], withAll: slopeFit(races).beta[1] };
})();

const competitiveSenate = (f: Faction) => races.filter((r) => r.office === 'Senate' && r.faction === f && r.cook !== null && Math.abs(r.cook) <= 1);
export const senateCompetitive = {
  progressive: competitiveSenate('progressive'),
  moderate: competitiveSenate('moderate'),
};

// Same-ballot pairs: one progressive and one moderate statewide Democrat in the same state.
export const pairs = (() => {
  const byState = new Map<string, Race[]>();
  for (const r of races) byState.set(r.st, [...(byState.get(r.st) ?? []), r]);
  const out: { prog: Race; mod: Race; diff: number; shareDiff: number }[] = [];
  for (const rs of byState.values()) {
    const p = rs.find((r) => r.faction === 'progressive'), m = rs.find((r) => r.faction === 'moderate');
    if (p && m && rs.length === 2) out.push({ prog: p, mod: m, diff: p.margin - m.margin, shareDiff: p.demPct - m.demPct });
  }
  return out.sort((a, b) => a.diff - b.diff);
})();

// t quantiles (two-sided 95%) for small samples
const T95 = [NaN, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228];
const summarisePairs = (ps: typeof pairs) => {
  const d = ps.map((p) => -p.diff); // moderate advantage
  const m = mean(d);
  const sd = Math.sqrt(d.reduce((s, v) => s + (v - m) ** 2, 0) / (d.length - 1));
  const t = T95[d.length - 1] ?? 1.96;
  return { mean: m, lo: m - (t * sd) / Math.sqrt(d.length), hi: m + (t * sd) / Math.sqrt(d.length), n: d.length };
};
export const pairSummary = summarisePairs(pairs);
// The same, leaving out pairs where either Democrat's faction label is low-confidence.
export const pairsLowConfidence = pairs.filter((p) => p.prog.lowConfidence || p.mod.lowConfidence);
export const pairSummaryConfident = summarisePairs(pairs.filter((p) => !p.prog.lowConfidence && !p.mod.lowConfidence));

// Swing on faction and controls across every race with exit-poll and opponent data (classical errors).
// The main version compares progressives with all other Democrats (moderates and mixed or unclear);
// a second version adds a mixed-or-unclear dummy so progressives are compared with moderates only.
// Drop-one: refit leaving out each progressive in turn, since there are so few.
export const statewideModel = (() => {
  const rows = races.filter((r) => r.white !== null && r.oppWeak !== null && r.repOfficeholder !== null);
  const names = ['const', 'progressive', 'pres24', 'd_inc', 'r_inc', 'senate', 'white', 'opp_weak', 'rep_officeholder'];
  const design = (rs: Race[], mixed: boolean) => rs.map((r) => [1, +(r.faction === 'progressive'), r.pres24, +r.dInc, +r.rInc, +(r.office === 'Senate'), r.white!, r.oppWeak!, r.repOfficeholder!, ...(mixed ? [+(r.faction === 'mixed-unclear')] : [])]);
  const fitOf = (rs: Race[], mixed = false) => ols(rs.map((r) => r.swing), design(rs, mixed), mixed ? [...names, 'mixed'] : names, 'classical');
  const fit = fitOf(rows);
  const prog = contrast(fit, { progressive: -1 }); // as a moderate advantage
  const officeholder = contrast(fit, { rep_officeholder: 1 });
  const vsModerate = contrast(fitOf(rows, true), { progressive: -1 });
  const progRows = rows.filter((r) => r.faction === 'progressive');
  const drops = progRows.map((p) => ({ st: p.st, e: contrast(fitOf(rows.filter((r) => r !== p)), { progressive: -1 }) }));
  const dropOne = {
    estMin: Math.min(...drops.map((d) => d.e.est)), estMax: Math.max(...drops.map((d) => d.e.est)),
    loMin: Math.min(...drops.map((d) => d.e.lo)),
    zeroIn: drops.filter((d) => d.e.lo <= 0.05).map((d) => d.st),
  };
  return { prog, officeholder, vsModerate, dropOne, n: fit.n, nProg: progRows.length,
    nMod: rows.filter((r) => r.faction === 'moderate').length, nMixed: rows.filter((r) => r.faction === 'mixed-unclear').length };
})();

// Sensitivity check: Third Way's post-election memo counts Talarico and Ossoff as moderates, where
// this page codes them mixed or unclear; it also names "Brown" among them, almost certainly Sherrod Brown.
// Recode all three and rerun the moderate-only comparisons.
export const THIRD_WAY_MODERATES = ['TX-Senate', 'GA-Senate', 'OH-Senate'];
export const thirdWay = (() => {
  const fac = (r: Race): Faction => (THIRD_WAY_MODERATES.includes(r.key) ? 'moderate' : r.faction);
  const rows = races.filter((r) => r.white !== null && r.oppWeak !== null && r.repOfficeholder !== null);
  const X = rows.map((r) => [1, +(fac(r) === 'progressive'), r.pres24, +r.dInc, +r.rInc, +(r.office === 'Senate'), r.white!, r.oppWeak!, r.repOfficeholder!, +(fac(r) === 'mixed-unclear')]);
  const fit = ols(rows.map((r) => r.swing), X, ['const', 'progressive', 'pres24', 'd_inc', 'r_inc', 'senate', 'white', 'opp_weak', 'rep_officeholder', 'mixed'], 'classical');
  const comp = races.filter((r) => r.office === 'Senate' && fac(r) === 'moderate' && r.cook !== null && Math.abs(r.cook) <= 1);
  return {
    vsModerate: contrast(fit, { progressive: -1 }),
    inModel: rows.filter((r) => THIRD_WAY_MODERATES.includes(r.key)).length,
    compModN: comp.length, compModMean: mean(comp.map((r) => r.swing)),
  };
})();

// ------------------------------------------------------------------ money

export const RATINGS = ['Tossup', 'Lean D', 'Likely D', 'Lean R', 'Likely R'];

export interface SenateMoney {
  key: string; st: string; dem: string; faction: Faction; rating: string;
  party: number; against: number; partyTotal: number; againstTotal: number; lcn: number;
  firstDate: string; nominated: string; demPct: number; repPct: number;
}

// Lower Costs Now was a joint vehicle: $30M of its $50M came from Senate Majority PAC and $20M from
// Future Forward (FactCheck.org, by Oct 14). Only SMP's share of its spending counts as party money.
export const LCN_PARTY_SHARE = 0.6;
export const senateMoneyRows: SenateMoney[] = senateMoney
  .filter((r) => r.office.startsWith('Senate') && RATINGS.includes(r.cook_final) && ['progressive', 'moderate', 'mixed-unclear'].includes(r.faction))
  .map((r) => {
    const all = num(r.pro_dem_party_gen) ?? 0, excl = num(r.pro_dem_party_gen_excl_lcn) ?? all;
    const lcn = all - excl, partyTotal = excl + LCN_PARTY_SHARE * lcn, vap = num(r.vap_2024)!;
    return {
    key: `${r.st}-Senate`, st: r.st, dem: r.democrat, faction: r.faction as Faction, rating: r.cook_final,
    party: partyTotal / vap, against: num(r.against_dem_total_per_vap) ?? 0,
    partyTotal, againstTotal: num(r.against_dem_total_gen) ?? 0, lcn,
    firstDate: r.party_ie_first_date, nominated: r.nomination_date_used,
    demPct: num(r.dem_pct)!, repPct: num(r.rep_pct)!,
  }; })
  .sort((a, b) => RATINGS.indexOf(a.rating) - RATINGS.indexOf(b.rating) || b.party - a.party);

export const senateMoneyBy = (st: string) => senateMoneyRows.find((r) => r.st === st);

export interface HouseMoney {
  code: string; dem: string; faction: Faction; rating: string; perVote: number; redToBlue: boolean; rtbDate: string; won: boolean;
  result: string; // won, lost, or leading / trailing while uncalled
}
const resultOf = (code: string, wonFlag: boolean) => {
  const s = seats.find((x) => x.code === code);
  if (!s || s.called) return wonFlag ? 'won' : 'lost';
  return s.margin > 0 ? 'leading, uncalled' : 'trailing, uncalled';
};
export const HOUSE_RATINGS = ['Toss-up', 'Lean', 'Likely'];
export const houseMoneyRows: HouseMoney[] = houseMoney
  .filter((r) => !HOUSE_EXCLUDE.has(r.code) && r.challenger_or_open === '1' && HOUSE_RATINGS.includes(r.rating_bucket) && num(r.estab_per_voter) !== null)
  .map((r) => ({
    code: r.code, dem: r.dem_nominee, faction: r.faction as Faction, rating: r.rating_bucket,
    perVote: num(r.estab_per_voter)!, redToBlue: r.red_to_blue === '1', rtbDate: r.red_to_blue_date, won: r.dem_won === '1',
    result: resultOf(r.code, r.dem_won === '1'),
  }));
export const houseMoneyMedian = (rating: string) =>
  median(houseMoneyRows.filter((r) => r.rating === rating && r.faction === 'moderate').map((r) => r.perVote))!;
export const houseMoneyBy = (code: string) => houseMoneyRows.find((r) => r.code === code);

// ------------------------------------------------------------------ estimates collected for the forest plot

export interface ForestRow { label: string; est: number; lo: number | null; hi: number | null; own: boolean; note: string }
const own = (label: string, e: Estimate | { mean: number; lo: number; hi: number }, note: string): ForestRow => {
  const est = 'est' in e ? e.est : e.mean;
  return { label, est, lo: e.lo, hi: e.hi, own: true, note };
};
export const forest: { group: string; rows: ForestRow[] }[] = [
  { group: 'Before 2026', rows: [
    { label: 'Split Ticket, Blue Dogs vs progressives, 2018–2024', est: 5, lo: null, hi: null, own: false, note: 'Jain in The Argument: "nearly 5" points' },
    { label: 'G. Elliott Morris, 2024 model', est: 1.25, lo: 1, hi: 1.5, own: false, note: 'Morris: about 1 to 1.5 points in 2024' },
    { label: 'Bonica and Grumbach, 2024 model', est: 0, lo: null, hi: null, own: false, note: 'Bonica and Grumbach: about zero' },
  ] },
  { group: '2026 House', rows: [
    { label: 'Split Ticket, Blue Dogs vs progressives', est: 3, lo: null, hi: null, own: false, note: 'The Argument: "a little over 3 points"' },
    own(`This page, broad factions, all ${houseModels.broadAll.n} seats`, houseModels.broadAll, ''),
    own(`This page, broad factions, ${houseModels.broadCompetitive.n} competitive seats`, houseModels.broadCompetitive, ''),
    own('This page, strict factions, all seats', houseModels.strictAll, ''),
    own('This page, strict, without 7 Hispanic-district outliers', houseModels.strictNoOutliers, ''),
    own('This page, strict, with Hispanic and college controls', houseModels.strictControls, ''),
  ] },
  { group: '2026 Senate and governor', rows: [
    own(`This page, ${pairSummary.n} same-ballot pairs`, pairSummary, ''),
    own(`This page, regression, progressives vs all other Democrats, ${statewideModel.n} races`, statewideModel.prog, ''),
    own('This page, same regression, progressives vs moderates only', statewideModel.vsModerate, ''),
    { label: 'CWCP, Sanders Senate endorsees on WAR', est: 8, lo: null, hi: null, own: false, note: 'About 8 points behind other Senate nominees' },
  ] },
];

// Red to Blue among challengers and open-seat nominees in competitive seats
const challengers = houseMoney.filter((r) => !HOUSE_EXCLUDE.has(r.code) && r.in_competitive_set === 'True' && r.challenger_or_open === '1');
export const redToBlue = (f: Faction) => {
  const rows = challengers.filter((r) => r.faction === f);
  return { yes: rows.filter((r) => r.red_to_blue === '1').length, n: rows.length };
};

// Close races in Trump+5-or-redder seats where the Democrat got under $1 per vote of outside help
export const nobodyHelped = (() => {
  const rows = houseMoney.filter((r) => {
    const p = num(r.pres24_margin), m = num(r.dem_margin);
    return !HOUSE_EXCLUDE.has(r.code) && p !== null && m !== null && p <= -5 && Math.abs(m) < 5 && (num(r.pro_dem_outside_per_voter) ?? 0) < 1;
  });
  const by = (f: Faction) => rows.filter((r) => r.faction === f).length;
  return { n: rows.length, unflagged: by('unflagged'), moderate: by('moderate'), progressive: by('progressive') + by('both') };
})();
export const receipts = (code: string) => num(houseMoney.find((r) => r.code === code)?.dem_receipts) ?? 0;
