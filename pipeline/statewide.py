"""Senate and governor races: public/data/statewide_2026.csv.

Port of the research scripts fetch_wiki.py (infobox parser), house_totals.py, build_base.py (results,
statewide House vote) and analysis.py (merge with faction coding, exit polls, outside spending).
Static inputs in static/statewide/: races.csv (one row per race: Wikipedia title, nominees, 2024
presidential margin, Cook final rating, incumbency, in the research build's page order),
manual_results.json (races whose infobox the parser cannot read), and the hand-coded faction,
exit-poll, outside-spending and opponent tables.
Fetched each run: the Wikipedia race pages (results) and the per-state 2026 House pages (statewide House vote).
"""
import json
import re

from common import STATIC, Guard, fmt_plain, read_csv, to_float
from house import state_title
from schema import STATEWIDE

S = STATIC / "statewide"
TRIM = r"\((?:American|Michigan|politician|pastor|Louisiana|businessman|Maine|U\.S\. senator|Rhode Island)[^)]*\)"
# Source of the statewide House vote per state, chosen in the research build after inspecting each page:
# "box" = sum of district general-election boxes, "first" = the page's first (statewide) infobox.
HOUSE_SRC = {"AL": "first", "AR": "first", "DE": "first", "GA": "first", "IA": "first", "KY": "box", "ME": "first",
             "MD": "first", "MI": "box", "MN": "first", "MS": "first", "MT": "first", "NE": "first", "NH": "first",
             "NJ": "first", "NY": "first", "NC": "box", "OH": "first", "OK": "box", "SC": "first", "SD": "first",
             "TX": "first", "VT": "first", "WV": "first", "WY": "first", "FL": "first", "CA": "first", "CO": "first",
             "CT": "first", "AZ": "first", "ID": "first"}
DEM_INDEP = ("Nebraska", "Idaho", "South Dakota", "Montana")
RESULT_COLS = ["dem_pct", "rep_pct", "dem_margin", "dem_margin_2party", "swing_vs_2024",
               "house_dem_margin_2party", "senate_minus_house_2party"]


def OFF(o):
    return "Senate" if o.startswith("Senate") else "Governor"


def races():
    return read_csv(S / "races.csv")


def wiki_titles():
    return [r["title"] for r in races()]


def house_state_titles():
    abbr = {r["st"] for r in races()}
    return [state_title(st) for st in sorted(abbr & set(HOUSE_SRC))]


# ---------------------------------------------------------------- parsers (fetch_wiki.py, build_base.py)
def infobox(t):
    i = t.find("{{Infobox election")
    if i < 0:
        return {}
    depth, j = 0, i
    while j < len(t):
        if t.startswith("{{", j):
            depth += 1
            j += 2
            continue
        if t.startswith("}}", j):
            depth -= 1
            j += 2
            if depth == 0:
                break
            continue
        j += 1
    box = t[i:j]
    fields = {}
    for m in re.finditer(r"\|\s*([a-z_]+\d*)\s*=\s*([^\n|]*(?:\{\{[^}]*\}\}[^\n|]*)*)", box):
        fields[m.group(1)] = m.group(2).strip()
    return fields


def clean(x):
    x = re.sub(r"<!--.*?(-->|$)|<br\s*/?>.*|'''|\{\{.*?\}\}", "", x or "")
    x = re.sub(r"\[\[([^|\]]*\|)?", "", x).replace("]]", "")
    x = re.sub(r"\(replaced[^)]*\)", "", x)
    return re.sub(r"\s+", " ", re.sub(TRIM, "", x)).strip()


def num(x):
    m = re.search(r"\d[\d,]*(\.\d+)?", (x or "").replace("'''", ""))
    return float(m.group(0).replace(",", "")) if m else None


def pct(x):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", x or "")
    return float(m.group(1)) if m else None


def house_first(t):
    box = t[t.find("{{Infobox election"):][:4000]
    seen = {}
    D = R = None
    for k, n, v in re.findall(r"\|\s*(party|popular_vote)(\d)\s*=\s*([^\n]*)", box):
        seen.setdefault(k + n, v)
    for n in "12":
        p = seen.get("party" + n, "").lower()
        v = num(re.sub(r"<.*", "", seen.get("popular_vote" + n, "")))
        if "democratic" in p:
            D = v
        elif "republican" in p:
            R = v
    return D, R


def box_totals(t):
    """house_totals.py: sum the general-election boxes on a state House page."""
    def n(s):
        s = re.sub(r"[^\d]", "", s or "")
        return int(s) if s else 0
    D = R = 0
    for blk in re.split(r"\{\{\s*Election box begin", t, flags=re.I)[1:]:
        head = blk[:400].lower()
        if "primary" in head or "general" not in head and "election" not in head:
            continue
        if "primary" in blk[:blk.find("}}") + 2].lower():
            continue
        end = blk.find("Election box end")
        blk = blk[:end if end > 0 else len(blk)]
        for m in re.finditer(r"\{\{\s*Election box (?:winning )?candidate[^}]*?\|\s*party\s*=\s*([^|}]*)[^}]*?\|\s*votes\s*=\s*([^|}]*)", blk, flags=re.I):
            p, v = m.group(1).lower(), n(m.group(2))
            if "democratic" in p:
                D += v
            elif "republican" in p:
                R += v
    return D, R


def surname_match(frozen, live):
    return frozen.split()[-1].lower() in (live or "").lower()


# ---------------------------------------------------------------- build
def build(wiki, prev):
    """wiki: {title: wikitext} for race pages and state House pages; prev: {(st, office): published row}.
    Returns (formatted rows, infoboxes {title: fields} in research page order)."""
    manual = json.loads((S / "manual_results.json").read_text(encoding="utf-8"))
    infoboxes = {}
    house_margin = {}
    for r in races():
        st = r["st"]
        if st in house_margin or st not in HOUSE_SRC:
            continue
        t = wiki.get(state_title(st))
        if t is None:
            house_margin[st] = "missing"
            continue
        hD, hR = box_totals(t) if HOUSE_SRC[st] == "box" else house_first(t)
        house_margin[st] = round(100 * (hD - hR) / (hD + hR), 2) if hD and hR else None

    base = []
    for r in races():
        title, st, stn, office = r["title"], r["st"], r["state"], r["office"]
        old = prev.get((st, office), {})
        rec = {k: r[k] for k in ("state", "st", "office", "dem_nominee", "dem_type", "rep_nominee", "pres2024_margin",
                                 "cook_final", "cook_num", "prior_incumbent", "dem_incumbent", "rep_incumbent")}
        f = infobox(wiki[title]) if title in wiki else None
        if f is not None:
            infoboxes[title] = f
        d = rr = None
        if f is not None:
            cands = [tuple(c) for c in manual[title]] if title in manual else [
                (clean(f.get(f"nominee{i}")), clean(f.get(f"party{i}")), pct(f.get(f"percentage{i}")), num(f.get(f"popular_vote{i}")))
                for i in "123456" if clean(f.get(f"nominee{i}"))]
            d = next((c for c in cands if re.search(r"Democratic|DFL|Farmer", c[1])), None)
            rr = next((c for c in cands if "Republican" in c[1]), None)
            if office == "Senate" and stn in DEM_INDEP:
                d = next((c for c in cands if "Independent" in c[1]), None)
            if d and rr and not (surname_match(r["dem_nominee"], d[0]) and surname_match(r["rep_nominee"], rr[0])):
                d = rr = None  # the page now names someone else: do not trust the parse
            if not (d and rr and d[2] is not None and rr[2] is not None):
                d = rr = None
        if d is None:
            rec.update({c: old.get(c, "") for c in ("dem_pct", "rep_pct", "dem_margin", "dem_margin_2party", "swing_vs_2024")})
        else:
            pm = to_float(r["pres2024_margin"])
            dm = round(d[2] - rr[2], 2)
            d2 = round(100 * (d[3] - rr[3]) / (d[3] + rr[3]), 2) if d[3] and rr[3] else None
            rec.update(dem_pct=d[2], rep_pct=rr[2], dem_margin=dm, dem_margin_2party=d2,
                       swing_vs_2024=round(dm - pm, 2) if pm is not None else None)
        hm = house_margin.get(st)
        if hm == "missing":
            rec["house_dem_margin_2party"] = old.get("house_dem_margin_2party", "")
        else:
            rec["house_dem_margin_2party"] = hm
        d2, hmf = to_float(rec["dem_margin_2party"]), to_float(rec["house_dem_margin_2party"])
        rec["senate_minus_house_2party"] = round(d2 - hmf, 2) if (hmf is not None and d2 is not None and office.startswith("Senate")) else None
        rec["results_source"] = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
        base.append(rec)
    base.sort(key=lambda x: (x["office"], x["state"]))

    def keyed(path, k1="state"):
        return {(x[k1], OFF(x["office"])): x for x in read_csv(path)}
    fac = {(x["state"], OFF(x["office"])): x for x in read_csv(S / "faction_supplement.csv") + read_csv(S / "faction.csv")}
    ex = keyed(S / "exit_polls.csv")
    sp = keyed(S / "outside_spending.csv")
    opp = {(x["st"], x["office"]): x for x in read_csv(S / "opponent_coding.csv")}
    guard = Guard("statewide_2026.csv", prev.values())
    rows = []
    for b in base:
        k = (b["st"], OFF(b["office"]))
        fr, er, sr, orow = fac.get(k, {}), ex.get(k, {}), sp.get(k, {}), opp.get(k, {})
        row = dict(
            state=b["state"], st=b["st"], office=b["office"], dem_nominee=b["dem_nominee"], dem_type=b["dem_type"], rep_nominee=b["rep_nominee"],
            dem_pct=b["dem_pct"], rep_pct=b["rep_pct"], dem_margin=b["dem_margin"], dem_margin_2party=b["dem_margin_2party"],
            pres2024_margin=b["pres2024_margin"], swing_vs_2024=b["swing_vs_2024"],
            faction=(fr.get("faction") or "").strip().lower(), faction_confidence=fr.get("confidence", ""),
            sanders_endorsed=fr.get("sanders_endorsed", ""), left_groups=fr.get("left_groups", ""), m4a=fr.get("m4a", ""),
            ice=fr.get("ice", ""), israel=fr.get("israel", ""), trans=fr.get("trans", ""), self_description=fr.get("self_description", ""),
            dem_incumbent=b["dem_incumbent"], rep_incumbent=b["rep_incumbent"], prior_incumbent=b["prior_incumbent"],
            opp_prior_office=fr.get("opponent_prior_office", ""), opp_favorability=fr.get("opponent_favorability", ""),
            opp_scandals=fr.get("opponent_scandals", ""), rep_officeholder=orow.get("rep_officeholder", ""),
            opp_weak_flag=orow.get("opp_weak", ""), opp_note=orow.get("note", ""), cook_final=b["cook_final"], cook_num=b["cook_num"],
            white_share_pct=er.get("white_share_pct", ""), dem_pct_white=er.get("dem_pct_white", ""),
            dem_pct_nonwhite=er.get("dem_pct_nonwhite", ""), exit_source=er.get("source_url", ""),
            outside_against_dem_usd=sr.get("outside_against_dem_usd", ""), outside_for_dem_usd=sr.get("outside_for_dem_usd", ""),
            total_outside_usd=sr.get("total_outside_usd", ""), spending_source=sr.get("source_url", ""), spending_notes=sr.get("notes", ""),
            house_dem_margin_2party=b["house_dem_margin_2party"], senate_minus_house_2party=b["senate_minus_house_2party"],
            faction_sources=fr.get("sources", ""), results_source=b["results_source"])
        for c in ("outside_against_dem_usd", "outside_for_dem_usd", "total_outside_usd"):
            row[c] = guard.check(f"{b['st']} {b['office']}", c, row[c], b["dem_nominee"])
        rows.append({c: fmt_plain(row[c]) for c in STATEWIDE})
    ordered = {t: infoboxes[t] for t in wiki_titles() if t in infoboxes}
    return rows, ordered
