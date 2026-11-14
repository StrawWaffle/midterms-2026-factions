# Data pipeline

`update.py` rebuilds the four CSVs in `public/data/` from live sources. It runs daily in
GitHub Actions (`.github/workflows/update.yml`, 07:00 UTC, also startable by hand). When a CSV
changes, the workflow commits it to `main` and starts the deploy workflow.

Standard library only (Python 3.12). The code ports the research scripts that first built these
files. On the inputs those scripts used, it reproduces the published CSVs byte for byte.

## What runs

| Output | Module | Ported from |
|---|---|---|
| `house_2026.csv` | `house.py` | `build_dataset.py`, plus the data part of `analyze.py` (derived faction columns) |
| `statewide_2026.csv` | `statewide.py` | `fetch_wiki.py`, `house_totals.py`, `build_base.py`, `analysis.py` |
| `senate_money_2026.csv` | `senate_money.py` | `statewide_money/scripts/build_dataset.py` |
| `house_money_2026.csv` | `house_money.py` | `house_money/scripts/{ielib,assign,build_house_money}.py`, plus the data part of `analyze_money.py` |

The House money file uses the House results built in the same run, and the Senate money file uses
the statewide results.

Other files: `sources.py` (downloads and cache), `net.py` (HTTP client), `fec.py` (reads the FEC
bulk files from their zips), `common.py` (CSV formatting, overrides), `schema.py` (the column order
of each CSV; the pipeline cannot write other columns).

## Fetched on each run

All downloads go to `pipeline/cache/`, which is gitignored.

- **NBC News (AP) House results.** NBC's per-state results feed
  (`nbcnews.com/firecracker/api/v2/state-results/2026-elections/<state>-house-results`), one
  request per state. It carries the same district figures as the district pages the research
  build read: votes, % of expected vote counted and the AP call. Alaska and Maine are the
  exception. Once AP tabulates ranked-choice rounds, the state feed shows the final round, so
  their three seats are read from the district pages, taking the first-round general-election
  race as the research build did.
- **California Secretary of State API.** Each California seat, used as the CA cross-check
  (`alt_dem_margin`).
- **Wikipedia, through the API (10 pages per request):**
  - the national 2026 House page: result text, winner check marks, fallback percentages;
  - the 50 state House pages: infobox cross-check and the statewide House vote;
  - the 71 Senate and governor race pages: results.
- **FEC 2026 bulk files:** `weball26.zip`, `cn26.zip`, `cm26.zip`, `pas226.zip` (party
  coordinated expenditures and contributions) and `independent_expenditure_2026.csv`. They are
  fetched with conditional GETs, so a file that has not changed is not downloaded again. The
  workflow keeps the cache between runs. Post-general campaign reports are due December 3, 2026.

Each request waits at least 2 seconds after the previous one to the same host. Failed requests
are retried 4 times with exponential backoff, honouring `Retry-After`. The User-Agent is
`midterms-2026-factions-updater/1.0`.

If a source fails, the affected rows keep their published values, the other files are still
rebuilt, and the script exits with status 1 so the workflow run shows as failed. When none of
the AP figures for a seat have changed, its `results_source` keeps its old date, so a daily run
with no new data changes nothing.

### Guard against falling money figures

Cumulative money figures only grow within a cycle. That covers candidate receipts and
disbursements, independent-expenditure totals, party coordinated and direct-contribution totals,
the 2026 all-in Senate race total, and the outside-spending columns in `statewide_2026.csv`.

If a new value is more than 10% below the published value for the same row and column, the
pipeline treats it as an upstream glitch. It keeps the published value and computes everything
derived from it (per-voter and per-adult figures, race totals, rating averages, ratios) from the
kept value. When a candidate's receipts are held back, that candidate's cash on hand and coverage
date are also kept from the same published report, so the row stays one consistent snapshot.

Each held-back value produces a warning naming the file, row, column, candidate and both values.
Warnings are printed in the run report, shown as GitHub Actions annotations, and written to
`pipeline/warnings.txt` (gitignored, rewritten on every run). They do not change the exit status.

If a drop is genuine (a refund or a corrected report), add a row to `static/overrides.csv` with
the value `ACCEPT_DROP` for that file, row and column. The fetched figure then goes through, and
everything derived from it is recomputed.

## Static inputs (`static/`)

These do not change, and are copied or derived once from the research folders:

| File | What it holds |
|---|---|
| `house/seats.csv` | The 410 D-vs-R seats: nominees, 2025 incumbent, incumbency code, all faction and endorsement flags and their sources. These were built from Wikipedia national, state, caucus and Justice Democrats pages, Ballotpedia, the NewDem Action Fund list and the WelcomePAC list as of 2026-11-14. |
| `house/downballot_pres24_2026_lines.csv` | The Downballot's 2024 presidential results on the 2026 district lines |
| `house/acs2024_*_cd119.dat` | ACS 2024 1-year tables B03003 and B15003, 119th-Congress districts only, with only the columns used |
| `statewide/races.csv` | One row per Senate or governor race: Wikipedia title, nominees, 2024 presidential margin, Cook final rating and incumbency. Rows are in the research build's page order, which matters for the Senate `total_votes_2026` lookup. |
| `statewide/manual_results.json` | Results read by hand for four races whose infobox the parser cannot read (AK Senate, AK, AR and CA governor) |
| `statewide/faction*.csv`, `exit_polls.csv`, `opponent_coding.csv` | Hand-coded faction, exit-poll and opponent tables |
| `statewide/outside_spending.csv` | Outside spending from VoteLog (Senate) and hand-collected figures (governor) |
| `senate_money/spender_classes.csv` | Senate IE spender classes |
| `senate_money/vap.csv` | Census civilian population 18+ by state, 2020/2022/2024 |
| `senate_money/senate_baselines.csv` | All-in Senate money per state in 2020, 2022 and 2024, computed from those cycles' FEC bulk files with the same method as 2026 |
| `house_money/nominee_fec_ids.csv` | Nominee-to-FEC-candidate-ID matches |
| `house_money/dccc_red_to_blue.csv`, `dccc_frontline.csv`, `house_ratings_final.csv` | DCCC program lists and final ratings |
| `overrides.csv` | Manual corrections applied to the finished CSVs |

## Running locally

```
python -I pipeline/update.py --dry-run    # fetch, rebuild and print what would change; write nothing
python -I pipeline/update.py              # fetch, rebuild, write the CSVs that changed
python -I pipeline/update.py --no-fetch   # rebuild from pipeline/cache/ without network access
python -I pipeline/update.py --no-fetch --out /tmp/out   # write the CSVs somewhere else
```

A full run makes about 120 requests and downloads about 60 MB of FEC files when they have
changed. It takes a few minutes.

## Adding a manual correction

- **To a fetched or computed value** (a vote count, a Red to Blue flag): add a row to
  `static/overrides.csv` with these columns:
  - `file`: for example `house_money_2026.csv`;
  - `key`: the seat code (`CA-22`) for the House files, or `<st> <office>` (`MI Senate`) for the
    statewide and Senate money files;
  - `column`;
  - `value`, exactly as it should appear in the CSV;
  - `note`, saying where the correction comes from.

  Overrides are applied last and win over every source. An override naming an unknown row or
  column stops the run. The CA-22 Red to Blue status and date are kept this way: the DCCC added
  Villegas on 2026-06-10, but the list has only its pre-primary pick, Jasmeet Bains.
- **To a static fact** (a nominee name, a faction flag, a rating): edit the file in `static/`
  directly.

Then run `python -I pipeline/update.py --no-fetch --dry-run` to check the change.
