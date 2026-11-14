"""Senate general-election money: public/data/senate_money_2026.csv.

Port of the research script statewide_money/scripts/build_dataset.py. Fetched each run: the FEC 2026
bulk files (weball26, cn26, cm26, pas226, independent_expenditure_2026.csv). Static inputs in
static/senate_money/: spender_classes.csv, vap.csv (Census civilian population 18+ by state, 2020/2022/2024)
and senate_baselines.csv (all-in Senate money per state in 2020/2022/2024, computed once from that
cycle's FEC bulk files with this same method). Governor rows reuse static/statewide/outside_spending.csv.
"""
import collections
import csv
import datetime as dt
import re
import unicodedata

import fec
from common import STATIC, Guard, fmt_plain, read_csv
from schema import SENATE_MONEY

S = STATIC / "senate_money"
# Date both nominees were set (start of the general-election window), from VoteLog's race pages.
# Other states fall back to the FEC election-type code on each expenditure (P = primary, G = general).
NOM_DATE = {"MI": "2026-08-04", "MN": "2026-08-11", "ME": "2026-07-25", "NC": "2026-03-03", "TX": "2026-05-26",
            "KS": "2026-08-04", "IA": "2026-06-02", "SC": "2026-08-25", "NH": "2026-09-08", "GA": "2026-06-16",
            "MS": "2026-03-10", "OH": "2026-05-05", "FL": "2026-08-18", "AK": "2026-08-18", "NE": "2026-05-12",
            "LA": "2026-06-27", "IL": "2026-03-17", "KY": "2026-05-19"}
# Groups as the research question lists them (the `faction` column is kept as-is).
Q_GROUP = {"MI": "progressive", "MN": "progressive", "ME": "progressive", "FL": "progressive", "KY": "progressive",
           "TN": "progressive", "MA": "progressive", "OR": "progressive", "IL": "progressive",
           "NC": "moderate", "KS": "moderate", "IA": "moderate", "SC": "moderate", "NH": "moderate", "AK": "moderate",
           "TX": "moderate", "GA": "moderate", "OH": "moderate", "MS": "moderate"}
COOK_NUM = {"Solid D": 3, "Likely D": 2, "Lean D": 1, "Tossup": 0, "Lean R": -1, "Likely R": -2, "Solid R": -3}
DSCC, NRSC = "C00042366", "C00027466"


def pdate(s):
    for f in ("%d-%b-%y", "%m/%d/%Y", "%m%d%Y"):
        try:
            return dt.datetime.strptime(s.strip(), f).date()
        except Exception:  # noqa: BLE001
            pass
    return None


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z ]", " ", s)


def surname(full):
    toks = [t for t in norm(full).split() if t not in ("JR", "SR", "II", "III", "IV")]
    return toks[-1] if toks else ""


def load_vap():
    vap = {}
    for r in read_csv(S / "vap.csv"):
        vap[r["state"]] = {y: int(r[f"vap_{y}"]) for y in (2020, 2022, 2024)}
    return vap


def load_cn(lines):
    out = []
    for l in lines:
        f = l.rstrip("\n").split("|")
        out.append(dict(id=f[0], name=f[1], party=f[2], year=f[3], st=f[4], office=f[5]))
    return out


def load_weball(lines):
    out = {}
    for l in lines:
        f = l.rstrip("\n").split("|")
        def fl(i):
            return float(f[i] or 0)
        out[f[0]] = dict(name=f[1], receipts=fl(5), disb=fl(7), coh=fl(10), indiv=fl(17), cvg=f[27])
    return out


def load_ie(reader):
    """Senate IEs, de-duplicated by content (tran_id is not unique across a filer's reports)."""
    rows = []
    for r in reader:
        if r["can_office"] != "S":
            continue
        try:
            r["amt"] = float(r["exp_amo"] or 0)
        except ValueError:
            continue
        rows.append(r)
    superseded = {r["prev_file_num"] for r in rows if r["prev_file_num"]}
    seen, out, dropped = {}, [], collections.Counter()
    for r in sorted(rows, key=lambda r: -int(r["file_num"] or 0)):  # newest filing first
        if r["file_num"] in superseded:
            dropped["superseded_file"] += r["amt"]
            continue
        if abs(r["amt"]) > 1e8:  # e.g. a $2bn line from an individual filer: data-entry junk
            dropped["junk_gt_100M"] += r["amt"]
            continue
        d = pdate(r["dissem_dt"]) or pdate(r["exp_date"]) or pdate(r["receipt_dat"])
        sig = (r["spe_id"], r["can_office_state"], surname(r["cand_name"].split(",")[0] if "," in r["cand_name"] else r["cand_name"]),
               r["sup_opp"], round(r["amt"], 2), d, r["pay"].upper().strip())
        if sig in seen and seen[sig] != r["file_num"]:
            dropped["dup_other_filing"] += r["amt"]
            continue
        seen[sig] = r["file_num"]
        r["date"] = d
        out.append(r)
    return out, dropped


def base_totals(year, cn, wb, ies):
    """All-in Senate money per state for one cycle: every Senate candidate's disbursements plus all Senate IEs."""
    ids = {x["id"]: x["st"] for x in cn if x["office"] == "S" and x["year"] == str(year)}
    tot = collections.defaultdict(float)
    for cid, s in ids.items():
        if cid in wb:
            tot[s] += wb[cid]["disb"]
    for r in ies:
        if r["cand_id"] in ids or (r["can_office_state"] in tot and r.get("fec_election_yr", str(year)) in (str(year), "")):
            s = ids.get(r["cand_id"], r["can_office_state"])
            tot[s] += r["amt"]
    return {s: a for s, a in tot.items() if a >= 1e5}


# Cumulative columns guarded against falling (see common.Guard); everything derived is computed afterwards.
GUARDED = (["dem_receipts", "dem_disbursements", "rep_receipts", "rep_disbursements"]
           + [f"pro_dem_{c}_{p}" for c in ("party", "prog", "other", "total") for p in ("gen", "pre")]
           + [f"against_dem_{c}_{p}" for c in ("party", "aipac", "crypto", "other", "total") for p in ("gen", "pre")]
           + ["pro_dem_crypto_gen", "pro_dem_party_gen_excl_lcn", "dem_coord_party", "rep_coord_party",
              "dscc_direct_contrib", "nrsc_direct_contrib"])


def who(row, col):
    return row["republican"] if col.startswith(("rep_", "nrsc_")) else row["democrat"]


def build(races, infob, paths, prev_rows=()):
    """races: published statewide rows; infob: {title: infobox fields} in research page order;
    paths: FEC bulk files from Sources.fec(); prev_rows: the published senate_money rows (for the guard)."""
    guard = Guard("senate_money_2026.csv", prev_rows)
    vap = load_vap()
    st_name = {r["st"]: r["state"] for r in races}
    classes = {r["spe_id"]: r for r in read_csv(S / "spender_classes.csv")}
    cm = {}
    for l in fec.lines(paths, "cm26"):
        f = l.rstrip("\n").split("|")
        cm[f[0]] = dict(name=f[1], dsgn=f[8], tp=f[9], pty=f[10])
    cn26 = load_cn(fec.lines(paths, "cn26"))
    wb26 = load_weball(fec.lines(paths, "weball26"))

    def find_cand(st, full, party_prefixes):
        sn = surname(full)
        c = [x for x in cn26 if x["st"] == st and x["office"] == "S" and x["year"] == "2026"
             and norm(x["name"]).split(" ")[0].strip() and sn in norm(x["name"]).split()]
        c = [x for x in c if x["party"][:3] in party_prefixes] or c
        first = norm(full).split()[0] if norm(full).split() else ""
        c = [x for x in c if first in norm(x["name"]).split()] or c
        c.sort(key=lambda x: -wb26.get(x["id"], {}).get("receipts", 0))
        return c[0]["id"] if c else None

    ie26, _dropped = load_ie(fec.ie_rows(paths, "utf-8", "replace"))
    ie_by_cand = collections.defaultdict(list)
    blank = collections.defaultdict(list)
    for r in ie26:
        if r["cand_id"]:
            ie_by_cand[r["cand_id"]].append(r)
        else:
            nm = r["cand_name"].split(",")[0] if "," in r["cand_name"] else r["cand_name"]
            blank[(r["can_office_state"], surname(nm))].append(r)
    ie_max_receipt = max(pdate(r["receipt_dat"]) for r in ie26 if pdate(r["receipt_dat"]))

    # party coordinated expenditures (24C) and direct contributions (24K) from party committees, regular reports
    coord = collections.defaultdict(float)
    direct = collections.defaultdict(float)
    coord_max = ""
    for l in fec.lines(paths, "pas226"):
        f = l.rstrip("\n").split("|")
        if f[5] == "24C":
            coord[f[16]] += float(f[14] or 0)
            d = f[13]
            coord_max = max(coord_max, d[4:] + d[:4])
        elif f[5] in ("24K", "24Z") and f[0] in (DSCC, NRSC):
            direct[(f[0], f[16])] += float(f[14] or 0)

    def total_votes(st, office):
        """Winner/loser popular vote over their percentage (Wikipedia infobox)."""
        for title, d in infob.items():
            if st_name.get(st, "##") not in title:
                continue
            if ("Senate" in office) != ("Senate" in title):
                continue
            if office == "Senate" and "special" in title:
                continue
            if "special" in office and "special" not in title:
                continue
            for i in (1, 2):
                pv = re.sub(r"[^\d]", "", d.get(f"popular_vote{i}", "") or "")
                pc = re.sub(r"[^\d.]", "", d.get(f"percentage{i}", "") or "")
                if pv and pc and float(pc) > 0:
                    return round(int(pv) / (float(pc) / 100))
        return ""

    outside_prior = read_csv(STATIC / "statewide" / "outside_spending.csv")
    out = []
    for race in races:
        st, office = race["st"], race["office"]
        stn = race["state"]
        v = vap.get(stn, {}).get(2024)
        row = dict(state=stn, st=st, office=office, democrat=race["dem_nominee"], republican=race["rep_nominee"],
                   faction=race["faction"], question_group=Q_GROUP.get(st, "") if "Senate" in office else "",
                   cook_final=race["cook_final"], cook_num=COOK_NUM.get(race["cook_final"], ""),
                   dem_pct=race["dem_pct"], rep_pct=race["rep_pct"], vap_2024=v,
                   total_votes_2026=total_votes(st, office))
        if "Senate" not in office:
            # Governor: FEC does not cover state races; carry the hand-collected outside-spending figures if any.
            for g in outside_prior:
                if g["state"] == st and g["office"] == "Governor":
                    row.update(gov_outside_for_dem=g["outside_for_dem_usd"], gov_outside_against_dem=g["outside_against_dem_usd"],
                               gov_outside_source=g["source_url"], gov_outside_notes=g["notes"][:300])
            if row.get("gov_outside_for_dem") or row.get("gov_outside_against_dem"):
                out.append(row)
            continue
        dname, rname = race["dem_nominee"], race["rep_nominee"]
        did = find_cand(st, dname, ("DEM", "DFL"))
        rid = find_cand(st, rname, ("REP",))
        row.update(dem_cand_id=did, rep_cand_id=rid,
                   dem_fec_name=wb26.get(did, {}).get("name", ""), rep_fec_name=wb26.get(rid, {}).get("name", ""))
        for cid, nm in ((did, dname), (rid, rname)):  # IE lines filed without a candidate ID
            if cid and (st, surname(nm)) in blank:
                ie_by_cand[cid].extend(blank.pop((st, surname(nm))))
        for side, cid in (("dem", did), ("rep", rid)):
            w = wb26.get(cid, {})
            row[f"{side}_receipts"] = round(w.get("receipts", 0)) if w else ""
            row[f"{side}_disbursements"] = round(w.get("disb", 0)) if w else ""
            row[f"{side}_cash_on_hand"] = round(w.get("coh", 0)) if w else ""
            row[f"{side}_fec_coverage_end"] = w.get("cvg", "")
        nom = dt.date.fromisoformat(NOM_DATE[st]) if st in NOM_DATE else None
        row["nomination_date_used"] = NOM_DATE.get(st, "FEC election code")
        agg = collections.defaultdict(float)
        party_dates = []
        party_by_month = collections.defaultdict(float)
        spenders = collections.defaultdict(float)
        party_sp = collections.defaultdict(float)
        prog_sp = collections.defaultdict(float)
        for cid in (did, rid):
            for r in ie_by_cand.get(cid, []):
                pro = (cid == did and r["sup_opp"] == "S") or (cid == rid and r["sup_opp"] == "O")
                if r["sup_opp"] not in ("S", "O"):
                    continue
                cls = classes.get(r["spe_id"], {}).get("class", "other")
                d = r["date"]
                gen = d > nom if nom and d else r["ele_type"].upper().startswith("G")
                ph = "gen" if gen else "pre"
                side = "pro" if pro else "anti"
                if pro:
                    cat = {"party": "party", "progressive": "prog"}.get(cls, "other")
                else:
                    cat = {"anti_party": "party", "anti_aipac": "aipac", "anti_crypto": "crypto"}.get(cls, "other")
                    if cls in ("party", "progressive"):  # a pro-Dem group attacking the Dem nominee (primary)
                        cat = "other"
                agg[f"{side}_{cat}_{ph}"] += r["amt"]
                agg[f"{side}_total_{ph}"] += r["amt"]
                if cls == "crypto_pro_dem" and pro:
                    agg[f"pro_crypto_{ph}"] += r["amt"]
                if pro and cls == "party" and d:
                    party_dates.append(d)
                    party_by_month[d.strftime("%Y-%m")] += r["amt"]
                nm = cm.get(r["spe_id"], {}).get("name", r["spe_nam"])
                if pro and cls == "party" and gen:
                    party_sp[nm] += r["amt"]
                if pro and cls == "progressive":
                    prog_sp[nm + (" (gen)" if gen else " (pre)")] += r["amt"]
                if gen:
                    spenders[(side, cm.get(r["spe_id"], {}).get("name", r["spe_nam"]))] += r["amt"]
        for side in ("pro", "anti"):
            cats = ("party", "prog", "other") if side == "pro" else ("party", "aipac", "crypto", "other")
            for cat in cats + ("total",):
                for ph in ("gen", "pre"):
                    row[f"{side}_dem_{cat}_{ph}" if side == "pro" else f"against_dem_{cat}_{ph}"] = round(agg.get(f"{side}_{cat}_{ph}", 0))
        row["pro_dem_crypto_gen"] = round(agg.get("pro_crypto_gen", 0))
        row["party_ie_first_date"] = min(party_dates).isoformat() if party_dates else ""
        tot_party = sum(party_by_month.values())
        row["party_ie_share_by_sep30"] = round(sum(a for m, a in party_by_month.items() if m <= "2026-09") / tot_party, 3) if tot_party else ""
        row["party_ie_by_month"] = "; ".join(f"{m}:{a/1e6:.2f}M" for m, a in sorted(party_by_month.items()))
        row["party_ie_breakdown_gen"] = "; ".join(f"{n} ${a/1e6:.2f}M" for n, a in sorted(party_sp.items(), key=lambda z: -z[1]))
        row["pro_dem_party_gen_excl_lcn"] = round(sum(a for n, a in party_sp.items() if n != "LOWER COSTS NOW"))
        row["progressive_ie_breakdown"] = "; ".join(f"{n} ${a:,.0f}" for n, a in sorted(prog_sp.items(), key=lambda z: -z[1]))
        row["dem_coord_party"] = round(coord.get(did, 0))
        row["rep_coord_party"] = round(coord.get(rid, 0))
        row["dscc_direct_contrib"] = round(direct.get((DSCC, did), 0))
        row["nrsc_direct_contrib"] = round(direct.get((NRSC, rid), 0))

        def top(s):
            return "; ".join([f"{n} ${a/1e6:.1f}M" for (sd, n), a in sorted(spenders.items(), key=lambda z: -z[1]) if sd == s and a >= 5e5][:5])
        key = f"{st} {office}"
        for c in GUARDED:
            row[c] = guard.check(key, c, row[c], who(row, c))
        for side in ("dem", "rep"):
            for c, kept in guard.keep_with(key, f"{side}_receipts", [f"{side}_cash_on_hand", f"{side}_fec_coverage_end"]).items():
                row[c] = int(kept) if kept.lstrip("-").isdigit() else kept
        row["top_pro_dem_gen"] = top("pro")
        row["top_against_dem_gen"] = top("anti")
        # Totals: general-election IEs on the two nominees + both campaigns' cycle disbursements + party coordinated
        cand = sum(x for x in (row["dem_disbursements"], row["rep_disbursements"]) if x != "")
        row["general_ie_total"] = row["pro_dem_total_gen"] + row["against_dem_total_gen"]
        row["race_total_2nominees"] = round(cand + row["general_ie_total"] + row["dem_coord_party"] + row["rep_coord_party"])
        if v:
            def pv(x):
                return round(x / v, 3)
            row["party_pro_dem_per_vap"] = pv(row["pro_dem_party_gen"])
            row["pro_dem_total_per_vap"] = pv(row["pro_dem_total_gen"])
            row["against_dem_total_per_vap"] = pv(row["against_dem_total_gen"])
            row["dem_receipts_per_vap"] = pv(row["dem_receipts"] or 0)
            row["race_total_per_vap"] = pv(row["race_total_2nominees"])
        row["coverage_note"] = (f"IEs: FEC bulk file incl. 24/48-hour reports received through {ie_max_receipt}; "
                                f"campaign figures through {row['dem_fec_coverage_end']} (pre-general); coordinated (24C) through {coord_max[4:6]}/{coord_max[6:]}/{coord_max[:4]}")
        out.append(row)

    # ---------- baseline: past Senate races per state, same method (all candidates + all IEs) ----------
    base = collections.defaultdict(dict)
    for r in read_csv(S / "senate_baselines.csv"):
        base[r["st"]][int(r["year"])] = float(r["all_in_total"])
    for s, a in base_totals(2026, cn26, wb26, ie26).items():
        base[s][2026] = a
    for row in out:
        if "Senate" not in row["office"]:
            continue
        s = row["st"]
        stn = row["state"]
        hist = []
        for y in (2020, 2022, 2024):
            a = base[s].get(y)
            vv = vap.get(stn, {}).get(y)
            if a and vv:
                row[f"senate{y}_all_in_total"] = round(a)
                row[f"senate{y}_all_in_per_vap"] = round(a / vv, 2)
                hist.append(a / vv)
        a26 = guard.check(f"{s} {row['office']}", "senate2026_all_in_total", base[s].get(2026, 0), "all candidates, race total")
        row["senate2026_all_in_total"] = round(a26)
        row["senate2026_all_in_per_vap"] = round(a26 / row["vap_2024"], 2) if row["vap_2024"] else ""
        row["past_senate_mean_per_vap"] = round(sum(hist) / len(hist), 2) if hist else ""
        row["ratio_2026_vs_past"] = round(a26 / row["vap_2024"] / (sum(hist) / len(hist)), 2) if hist and row["vap_2024"] else ""
    by_rating = collections.defaultdict(list)
    for row in out:
        if "Senate" in row["office"] and row.get("senate2026_all_in_per_vap") not in ("", None):
            by_rating[row["cook_final"]].append(row)
    for row in out:
        if "Senate" not in row["office"]:
            continue
        peers = by_rating.get(row["cook_final"], [])
        if peers:
            m = sum(p["senate2026_all_in_per_vap"] for p in peers) / len(peers)
            mp = sum(p.get("party_pro_dem_per_vap", 0) for p in peers) / len(peers)
            row["rating_mean_all_in_per_vap"] = round(m, 2)
            row["ratio_vs_rating_mean"] = round(row["senate2026_all_in_per_vap"] / m, 2) if m else ""
            row["rating_mean_party_pro_dem_per_vap"] = round(mp, 3)
    return [{c: fmt_plain(r.get(c, "")) for c in SENATE_MONEY} for r in out]


def write_baselines(year, cn_lines, weball_lines, ie_path, out_rows):
    """Helper used once to build static/senate_baselines.csv from a past cycle's bulk files."""
    with open(ie_path, encoding="utf-8", errors="replace") as fh:
        ies = load_ie(csv.DictReader(fh))[0]
    for s, a in sorted(base_totals(year, load_cn(cn_lines), load_weball(weball_lines), ies).items()):
        out_rows.append({"st": s, "year": year, "all_in_total": repr(a)})
