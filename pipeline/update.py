"""Refresh the four CSVs in public/data/ from live sources.

    python -I pipeline/update.py              fetch everything, rebuild, write files that changed
    python -I pipeline/update.py --no-fetch   rebuild from pipeline/cache/ only (no network)
    python -I pipeline/update.py --dry-run    fetch and rebuild, print the diff, write nothing

Exit status: 0 when every source was read (whether or not anything changed), 1 when a source failed.
Rows whose source failed keep their published values, and the files that could be rebuilt are still written.
"""
import argparse
import collections
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script directory off sys.path

import house  # noqa: E402
import house_money  # noqa: E402
import net  # noqa: E402
import schema  # noqa: E402
import senate_money  # noqa: E402
import statewide  # noqa: E402
from common import DATA, HERE, WARNINGS, apply_overrides, read_csv, row_key, to_csv_text  # noqa: E402
from sources import CACHE, Sources  # noqa: E402

FILES = {"house_2026.csv": schema.HOUSE, "statewide_2026.csv": schema.STATEWIDE,
         "senate_money_2026.csv": schema.SENATE_MONEY, "house_money_2026.csv": schema.HOUSE_MONEY}


def read_text(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""


def diff_summary(name, old_rows, new_rows, limit=12):
    old = {row_key(r): r for r in old_rows}
    new = {row_key(r): r for r in new_rows}
    lines = []
    added, removed = sorted(set(new) - set(old)), sorted(set(old) - set(new))
    if added:
        lines.append(f"  added rows: {', '.join(added)}")
    if removed:
        lines.append(f"  removed rows: {', '.join(removed)}")
    by_col = collections.Counter()
    examples = []
    changed_rows = 0
    for k in new:
        if k not in old:
            continue
        cols = [c for c in new[k] if new[k][c] != old[k].get(c, "")]
        if cols:
            changed_rows += 1
            by_col.update(cols)
            for c in cols:
                if len(examples) < limit:
                    examples.append(f"    {k} {c}: {old[k].get(c, '')[:60]!r} -> {new[k][c][:60]!r}")
    if changed_rows:
        lines.append(f"  {changed_rows} rows changed; columns: " + ", ".join(f"{c} ({n})" for c, n in by_col.most_common()))
        lines += examples
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-fetch", action="store_true", help="use only what is already in the cache")
    ap.add_argument("--dry-run", action="store_true", help="print what would change, write nothing")
    ap.add_argument("--cache", type=Path, default=CACHE, help="cache directory (default pipeline/cache)")
    ap.add_argument("--out", type=Path, default=DATA, help="where to write the CSVs (default public/data)")
    args = ap.parse_args()

    prev = {name: read_csv(DATA / name) if (DATA / name).exists() else [] for name in FILES}
    src = Sources(fetch=not args.no_fetch, cache=args.cache)

    net.log("Wikipedia pages ...")
    titles = list(dict.fromkeys(house.wiki_titles() + statewide.wiki_titles() + statewide.house_state_titles()))
    wiki = src.wikitexts(titles)
    net.log("NBC News results ...")
    nbc = src.nbc_states(house.districts_by_state())
    net.log("California SoS ...")
    ca = src.ca_districts(house.ca_districts_needed())
    net.log("FEC bulk files ...")
    paths = src.fec()

    built = {}
    built["house_2026.csv"] = house.build(nbc, ca, wiki, {r["code"]: r for r in prev["house_2026.csv"]})
    sw_rows, infob = statewide.build(wiki, {(r["st"], r["office"]): r for r in prev["statewide_2026.csv"]})
    built["statewide_2026.csv"] = sw_rows
    if len(paths) == len(FEC_KEYS):
        rows = senate_money.build(sw_rows, infob, paths, prev["senate_money_2026.csv"])
        old = {row_key(r): r for r in prev["senate_money_2026.csv"]}
        missing = {(r["st"], r["office"]) for r in statewide.races() if r["title"] not in infob}
        for r in rows:  # total votes come from the race page; keep the published value if the page was unavailable
            if (r["st"], r["office"]) in missing and row_key(r) in old:
                r["total_votes_2026"] = old[row_key(r)]["total_votes_2026"]
        built["senate_money_2026.csv"] = rows
        built["house_money_2026.csv"] = house_money.build(built["house_2026.csv"], paths, prev["house_money_2026.csv"])
    else:
        net.log("FEC files unavailable: money files left as they are")

    report = []
    args.out.mkdir(parents=True, exist_ok=True)
    for name, rows in built.items():
        apply_overrides(rows, name, FILES[name])
        text = to_csv_text(rows, FILES[name])
        old_text = read_text(DATA / name)
        if text == old_text:
            report.append(f"{name}: unchanged")
            if args.out != DATA and not args.dry_run:
                (args.out / name).write_text(text, encoding="utf-8", newline="")
            continue
        report.append(f"{name}: CHANGED")
        report += diff_summary(name, prev[name], rows)
        if not args.dry_run:
            (args.out / name).write_text(text, encoding="utf-8", newline="")
    # Guard warnings: printed, written to pipeline/warnings.txt (gitignored), annotated in GitHub Actions.
    (HERE / "warnings.txt").write_text("".join(w + "\n" for w in WARNINGS), encoding="utf-8")
    if WARNINGS:
        report.append(f"{len(WARNINGS)} guard warnings (published values kept; see pipeline/warnings.txt):")
        report += [f"  {w}" for w in WARNINGS]
        if os.environ.get("GITHUB_ACTIONS"):
            for w in WARNINGS:
                print(f"::warning::{w}")
    if src.failures:
        report.append(f"{len(src.failures)} source failures (published values kept for those rows):")
        report += [f"  {f}" for f in src.failures[:30]]
    print("\n".join(report))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("```\n" + "\n".join(report) + "\n```\n")
    return 1 if src.failures else 0


FEC_KEYS = ("weball26", "cn26", "cm26", "pas226", "ie26")

if __name__ == "__main__":
    sys.exit(main())
