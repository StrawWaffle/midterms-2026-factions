# Moderates, progressives and the 2026 wave

A data page asking whether moderate or progressive Democrats drove the November 3, 2026 midterm wave, and whether party groups funded progressive nominees. It compares every House race with a Democrat against a Republican and the Senate and governor races against the 2024 presidential result, with outside spending from FEC filings, and collects the published analyses.

Live page: https://strawwaffle.github.io/midterms-2026-factions/

The site is built with [Astro](https://astro.build) and [d3](https://d3js.org), and published to GitHub Pages by `.github/workflows/deploy.yml` on every push to `main`.

## How the page is built

- `src/lib/data.ts` reads the four CSVs in `public/data/` at build time.
- `src/lib/analysis.ts` computes every number that comes from the data, including the regressions (`src/lib/stats.ts`: OLS with HC1 robust standard errors). The prose in `src/pages/index.astro` takes its numbers from here, so text and charts follow the data when it updates. Figures quoted from published analyses are written into the text with their sources.
- `src/components/*Chart.astro` and `HouseStrip.astro` draw the charts as inline SVG with d3 scales at build time, so the page reads fully without JavaScript. Faction colors are CSS variables (`src/styles/site.css`), validated as a set for color-vision deficiency, and every faction also has its own shape.
- `src/scripts/app.ts` (d3-selection) adds the interactions: tooltips on hover or tap; selecting a race (click a mark, or use the "Find a race" box) marks it in every chart and keeps its numbers in a bar at the bottom of the screen; legend buttons highlight one faction in every chart while the others fade and the axes stay fixed; Escape clears.

Local preview: `npm install`, then `npm run dev`.

## Data

`public/data/` holds the data the page is built from. Each row lists its sources.

| file | rows |
|---|---|
| `house_2026.csv` | House seats with a Democrat against a Republican: AP results via NBC News, 2024 presidential margin on the 2026 lines (The Downballot), faction flags from caucus rosters and endorsement lists, ACS demographics |
| `statewide_2026.csv` | Senate and governor races: results, faction coding, exit-poll white share, opponent coding, outside spending |
| `senate_money_2026.csv` | Senate general-election outside spending by spender type from FEC bulk files, per adult, with past-cycle baselines |
| `house_money_2026.csv` | House general-election party and outside spending per vote cast, Red to Blue status and race ratings |

Results are unofficial until certified. FEC campaign receipts and party coordinated spending lag; post-general reports were due December 3, 2026.

## Updates

`pipeline/update.py` refetches what changes (NBC results feeds, statewide results, the FEC bulk files), rebuilds the four CSVs from those plus the fixed inputs in `pipeline/static/`, and changes nothing when nothing new has come in. `.github/workflows/update.yml` runs it daily at 07:00 UTC on GitHub Actions; when the data changed it commits `public/data` as StrawWaffle and starts the deploy. Cumulative FEC figures are never allowed to fall by more than 10%: a drop like that is treated as an FEC glitch, the published value is kept and a warning is logged. Details, local runs and manual corrections: [`pipeline/README.md`](pipeline/README.md).

Each build publishes `/version.json` with fingerprints of its data and code. An open page checks it every ten minutes and when the tab comes back into view, and offers a reload when a newer build is out.
