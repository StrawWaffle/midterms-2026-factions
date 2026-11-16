// Helpers for the page that checks Mehdi Hasan's claims.
import { CLAIMS, type Claim, type Theme, type Verdict } from './hasanClaims';

export const VIDEOS = {
  zeteo: {
    title: 'Zeteo monologue',
    short: 'Zeteo video',
    when: 'November 13, 2026',
    url: 'https://x.com/mehdirhasan/status/2121382704105267425',
    alt: 'https://zeteo.com/p/debunked-mehdi-dismantles-the-myth',
  },
  fp: {
    title: 'Fast Politics with Molly Jong-Fast',
    short: 'Fast Politics',
    when: 'recorded November 13, 2026',
    url: 'https://www.youtube.com/watch?v=rN2etNsrucM',
    alt: '',
  },
} as const;

export const THEMES: Record<Theme, string> = {
  framing: 'What the other side said',
  opponents: 'Who they ran against',
  race: 'Race and racism',
  money: 'Money',
  media: 'Media coverage',
  minnesota: 'Minnesota',
  wins: 'Progressive wins in red seats',
  moderates: 'What counts as a moderate',
  schumer: 'Schumer and the leadership fight',
  maine: 'Maine and Collins',
};

export const VERDICTS: Verdict[] = ['True', 'Mostly true', 'Partly true', 'Misleading', 'False', 'Unsupported', 'Opinion'];

export const verdictClass = (v: Verdict) =>
  v === 'True' || v === 'Mostly true' ? 'v-true'
  : v === 'Partly true' ? 'v-partly'
  : v === 'Misleading' || v === 'False' ? 'v-false'
  : 'v-other';

export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

export const tally = VERDICTS.map((v) => ({ verdict: v, n: CLAIMS.filter((c) => c.verdict === v).length })).filter((t) => t.n > 0);

// Sections: one per video, then one per theme, themes in the order they first come up and
// cards in video order within each theme.
export const sections = (['zeteo', 'fp'] as const).map((video) => {
  const cards = CLAIMS.filter((c) => c.video === video).sort((a, b) => a.start - b.start);
  const themes: { theme: Theme; cards: Claim[] }[] = [];
  for (const c of cards) {
    const t = themes.find((x) => x.theme === c.theme);
    if (t) t.cards.push(c);
    else themes.push({ theme: c.theme, cards: [c] });
  }
  return { video, themes };
});
