# Moderates, progressives and the 2026 wave

A data page asking whether moderate or progressive Democrats drove the November 3, 2026 midterm wave. It compares every House race with a Democrat against a Republican (410 seats) and 65 Senate and governor races against the 2024 presidential result, and collects the published analyses.

Live page: https://strawwaffle.github.io/midterms-2026-factions/

## Build

```
python -I build.py
```

Standard library only. `build.py` reads `data/*.csv`, draws the charts as inline SVG into `page.html`, and writes `site/index.html` plus copies of the data. GitHub Actions runs the same command on every push to `main` and deploys `site/` to GitHub Pages.

## Data

- `data/house_2026.csv`: one row per House seat with a Democrat against a Republican. Results are AP counts from NBC News pages collected November 14, 2026 (unofficial). 2024 presidential margins on the 2026 maps come from The Downballot. Faction flags come from caucus rosters and endorsement lists (Justice Democrats, DSA, Sanders, Our Revolution, Progressive Caucus PAC, New Democrat Action Fund, Blue Dog PAC, WelcomePAC).
- `data/statewide_2026.csv`: Senate and governor races, with faction coding, opponent notes, exit-poll white share and outside spending where available. Each row lists its sources.

- `data/senate_money_2026.csv` and `data/house_money_2026.csv`: general-election outside spending by spender type (party committees and party super PAC networks, progressive groups, moderate groups, others, and spending against the Democrat), from FEC bulk files through November 12, 2026, with Red to Blue status and race ratings. Campaign receipts and party coordinated spending stop at mid-October until the post-general reports due December 3, 2026.

Results were unofficial when collected, and some seats were still counting.
