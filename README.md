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

Results were unofficial when collected, and some seats were still counting.
