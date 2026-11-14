// One entry per House seat and statewide race: what the search box offers and what the
// selection bar shows when that race is picked. Keys match data-key on chart marks.
import { seats, races, houseMoneyBy, senateMoneyBy } from './analysis';
import { FACTION } from './factions';
import { signed, usd } from './format';

export interface Entity { key: string; label: string; facts: string }

const result = (m: number) => (m >= 0 ? `won by ${m.toFixed(1)}` : `lost by ${Math.abs(m).toFixed(1)}`);

export const entities: Entity[] = [
  ...seats.map((s) => {
    const money = houseMoneyBy(s.code);
    return {
      key: s.code,
      label: `${s.code} · ${s.dem} (D) vs ${s.rep} (R)`,
      facts: [
        FACTION[s.faction].label,
        result(s.margin) + (s.called ? '' : ' (not yet called)'),
        `2024 presidential ${signed(s.pres24)}`,
        `ran ${signed(s.overperf)} ahead of Harris`,
        money ? `party money ${usd(money.perVote)} per vote` : '',
      ].filter(Boolean).join(' · '),
    };
  }),
  ...races.map((r) => {
    const money = r.office === 'Senate' ? senateMoneyBy(r.st) : undefined;
    return {
      key: r.key,
      label: `${r.state} ${r.office} · ${r.dem} (D)`,
      facts: [
        FACTION[r.faction].label,
        result(r.margin),
        `2024 presidential ${signed(r.pres24)}`,
        `swing ${signed(r.swing)}`,
        money ? `party money ${usd(money.party)} per adult against ${usd(money.against)} spent against` : '',
      ].filter(Boolean).join(' · '),
    };
  }),
];
