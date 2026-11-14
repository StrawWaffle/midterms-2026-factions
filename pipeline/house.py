"""House D-vs-R results: public/data/house_2026.csv.

Port of the research scripts build_dataset.py (results, cross-checks, 2024 baseline, ACS) and the
data-producing part of analyze.py (derived faction columns). What does not change is read from
static/house/: the 410 seats with their nominees, incumbency and faction flags (seats.csv), The
Downballot's 2024 presidential results on the 2026 lines, and ACS 2024 shares.
What is fetched each run: NBC News/AP results, the California SoS API (cross-check) and the Wikipedia
national and per-state 2026 House pages (result text, winner check marks, infobox cross-check).
"""
import csv
import re

from common import STATIC, fmt_pandas, read_csv, to_float
from schema import HOUSE, HOUSE_BOOL, HOUSE_FLOAT

ABBR = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
AT_LARGE = {"AK", "DE", "ND", "SD", "VT", "WY"}
# States whose 2026 lines differ from 2024 (Wikipedia summary table + Downballot sheet both agree)
REDRAWN = {"AL", "CA", "FL", "LA", "NC", "OH", "TN", "TX", "UT"}
FIPS = {"AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10",
        "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20",
        "KY": "21", "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
        "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36",
        "NC": "37", "ND": "38", "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
        "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
        "WI": "55", "WY": "56"}
MAIN_TITLE = "2026 United States House of Representatives elections"
# Columns that come from fetched sources; when a source is unavailable they keep the published value.
NBC_COLS = ["dem_votes", "rep_votes", "total_votes", "dem_pct", "rep_pct", "dem_margin", "pct_expected_vote", "called",
            "nbc_dem_name", "nbc_rep_name", "results_source", "nbc_winner_party"]
ALT_COLS = ["alt_dem_margin", "alt_source"]


def state_title(st):
    name = ABBR[st]
    return f"2026 United States House of Representatives election{'' if st in AT_LARGE else 's'} in {name}"


def kind(col):
    if col in HOUSE_FLOAT:
        return "float"
    if col in HOUSE_BOOL:
        return "bool"
    return "int" if col in INT_COLS else "str"


INT_COLS = set("""district n_dem n_rep total_votes called source_disagree redrawn_2026 pres24_from_memory jd_endorsed
dsa_endorsed sanders_endorsed ourrev_endorsed cpcpac_endorsed newdem_endorsed bluedog_endorsed welcome_endorsed
endorse_lines_found cpc_member newdem_member bluedog_member d_inc r_inc prog mod prog_strict mod_strict prog_member
mod_member prog_only mod_only prog_mod_both prog_strict_only mod_strict_only prog_strict_mod_strict_both
prog_member_only mod_member_only prog_member_mod_member_both flip d_win_trump_seat""".split())


# ---------------------------------------------------------------- wikitext helpers (from build_dataset.py)
def strip_wiki(s):
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\{\{sortname\|([^|}]*)\|([^|}]*)[^}]*\}\}", r"\1 \2", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = s.replace("'''", "").replace("''", "").replace("&nbsp;", " ")
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(s.split())


def num(s):
    s = strip_wiki(s or "").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_main(text):
    """One record per district from the per-state summary tables on the national page."""
    start = text.index("==Alabama==")
    rows = {}
    bodies, cur = {}, None
    for chunk in re.split(r"^\|-.*$", text[start:], flags=re.M):
        chunk = chunk.split("\n|}")[0]
        m = re.match(r"\s*!\s*(?:rowspan=\d+\s*\|)?\s*\{\{[Uu]shr\|([A-Z]{2})\|(\w+)\|X\}\}", chunk)
        if m:
            dist = m.group(2)
            cur = (m.group(1), 0 if dist.upper() in ("AL", "AT-LARGE") else int(dist))
            bodies[cur] = chunk
        elif cur and re.search(r"^\|\s*style=[^|]*\|\s*(Republican|Democratic|DFL)\s*$", chunk, re.M):
            bodies[cur] += "\n" + chunk
            cur = None
        else:
            cur = None
    for (st, d), body in bodies.items():
        res = [strip_wiki(x.split("|", 2)[-1]) for x in
               re.findall(r"^\|[^\n]*(?:Incumbent|New seat|New district)[^\n]*", body, re.M | re.I)]
        cands = []
        for cm in re.finditer(r"^\*\s*\{\{[Pp]arty stripe\|[^}]*\}\}(\{\{aye\}\})?\s*(.*?)\s*\(([^()]*)\)\s*([\d.]+%)?\s*$", body, re.M):
            cands.append({"name": strip_wiki(cm.group(2)), "party": cm.group(3).strip(),
                          "won": bool(cm.group(1)), "pct": num(cm.group(4))})
        rows[(st, d)] = {"result_text": " / ".join(res), "cands": cands}
    return rows


def district_sections(text, st):
    if st in AT_LARGE:
        return {0: text}
    heads = [(m.start(), int(m.group(1))) for m in
             re.finditer(r"^={2,3}\s*District\s+(\d+)\s*={2,3}\s*$", text, re.M)]
    out = {}
    for i, (pos, d) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        nxt = re.search(r"^==[^=].*==\s*$", text[pos + 5:end], re.M)
        seg = text[pos:end]
        if nxt and not re.match(r"==\s*District", nxt.group(0)):
            seg = text[pos:pos + 5 + nxt.start()]
        out[d] = seg
    return out


def parse_infobox(seg):
    m = re.search(r"\{\{Infobox election(.*?)\n\}\}", seg, re.S)
    if not m:
        return None
    params = {}
    for pm in re.finditer(r"^\|\s*(\w+)\s*=\s*(.*)$", m.group(1), re.M):
        params[pm.group(1)] = pm.group(2).strip()
    noms = []
    for k in range(1, 7):
        if f"nominee{k}" not in params:
            continue
        party = params.get(f"party{k}", "")
        noms.append({
            "party": "D" if "Democratic" in party else ("R" if "Republican" in party else party),
            "pct": num(params.get(f"percentage{k}")),
        })
    return {"noms": noms}


def nbc_result(state_feed, d):
    out = {"dem_votes": None, "rep_votes": None, "total_votes": None, "dem_pct": None, "rep_pct": None,
           "dem_margin": None, "pct_expected_vote": None, "called": None, "nbc_dem_name": "",
           "nbc_rep_name": "", "results_source": "", "nbc_winner_party": ""}
    dd = state_feed["districts"]
    race = dd.get(f"{d or 1:02d}") or (next(iter(dd.values())) if len(dd) == 1 else None)
    if not race:
        return None
    cs = race.get("candidates", [])
    dem = [c for c in cs if c.get("party") == "Dem"]
    rep = [c for c in cs if c.get("party") == "Rep"]
    tot = race.get("totalVote") or sum(c.get("vote") or 0 for c in cs)
    out["total_votes"] = tot
    out["pct_expected_vote"] = race.get("percentIn")
    out["called"] = int(bool(race.get("isCalled")))
    win = [c for c in cs if c.get("isWinner")]
    out["nbc_winner_party"] = {"Dem": "D", "Rep": "R"}.get(win[0].get("party"), win[0].get("party")) if win else ""
    if len(dem) == 1 and len(rep) == 1 and tot:
        out["dem_votes"], out["rep_votes"] = dem[0]["vote"], rep[0]["vote"]
        out["dem_pct"] = round(100 * dem[0]["vote"] / tot, 2)
        out["rep_pct"] = round(100 * rep[0]["vote"] / tot, 2)
        out["dem_margin"] = round(out["dem_pct"] - out["rep_pct"], 2)
        out["nbc_dem_name"], out["nbc_rep_name"] = dem[0]["name"], rep[0]["name"]
        out["results_source"] = "NBC News/AP " + state_feed["fetched"][:10]
    return out


# ---------------------------------------------------------------- static inputs
def load_pres():
    pres = {}
    with open(STATIC / "house" / "downballot_pres24_2026_lines.csv", encoding="utf-8") as f:
        for r in csv.reader(f):
            if r and re.match(r"^[A-Z]{2}-(\d+|AL)$", r[0]):
                st, d = r[0].split("-")
                d = 0 if d == "AL" else int(d)
                h, t = num(r[7]), num(r[8])
                pres[(st, d)] = (h, t, None if h is None else round(h - t, 2))
    return pres


def acs_shares():
    """ACS 2024 1-year, 119th-Congress districts: Hispanic share (B03003) and BA+ share of 25+ (B15003)."""
    def load(fn):
        with open(STATIC / "house" / fn, encoding="utf-8") as f:
            return {r["GEO_ID"]: r for r in csv.DictReader(f, delimiter="|") if r["GEO_ID"].startswith("5001900US")}
    hisp, edu = load("acs2024_b03003_cd119.dat"), load("acs2024_b15003_cd119.dat")
    out = {}
    for g, r in hisp.items():
        e = edu.get(g)
        ba = sum(float(e[f"B15003_E0{k}"]) for k in (22, 23, 24, 25)) / float(e["B15003_E001"]) if e else None
        out[g[-4:]] = (round(100 * float(r["B03003_E003"]) / float(r["B03003_E001"]), 1),
                       None if ba is None else round(100 * ba, 1))
    return out


def seats():
    return read_csv(STATIC / "house" / "seats.csv")


def districts_by_state():
    out = {}
    for s in seats():
        out.setdefault(s["state"], []).append(int(s["district"]))
    return out


def ca_districts_needed():
    return sorted(int(s["district"]) for s in seats() if s["state"] == "CA")


def wiki_titles():
    return [MAIN_TITLE] + [state_title(st) for st in ABBR]


# ---------------------------------------------------------------- build
def build(nbc, ca, wiki, prev):
    """nbc: {st: feed}, ca: {district: json}, wiki: {title: wikitext}, prev: {code: published row}.
    Returns formatted rows in published order."""
    main_rows = parse_main(wiki[MAIN_TITLE]) if MAIN_TITLE in wiki else None
    sections = {st: district_sections(wiki[state_title(st)], st) for st in ABBR if state_title(st) in wiki}
    pres = load_pres()
    acs = acs_shares()
    rows = []
    for s in seats():
        st, d, code = s["state"], int(s["district"]), s["code"]
        old = prev.get(code, {})
        rec = {"state": st, "district": d, "code": code, "dem_nominee": s["dem_nominee"], "rep_nominee": s["rep_nominee"],
               "n_dem": s["n_dem"], "n_rep": s["n_rep"]}
        mr = main_rows.get((st, d)) if main_rows is not None else None
        wiki_winner = next((c["party"][:1] for c in mr["cands"] if c["won"]), "") if mr else None
        rec["prior_party"] = s["prior_party"]
        rec["incumbent_2025"] = s["incumbent_2025"]
        rec["result_text"] = mr["result_text"][:160] if mr else old.get("result_text", "")

        nb = nbc_result(nbc[st], d) if st in nbc else None
        if nb is None:  # feed unavailable: keep the published figures
            nb = {c: old.get(c) for c in NBC_COLS}
        elif old and all(fmt_pandas(nb[c], kind(c)) == old.get(c) for c in NBC_COLS if c != "results_source"):
            nb["results_source"] = old.get("results_source", nb["results_source"])  # unchanged figures keep their date
        rec.update(nb)

        alt_m, alt_src, have_alt = None, "", True
        if st == "CA":
            js = ca.get(d)
            if js is None:
                have_alt = False
            else:
                dpc = next((num(c["Percent"]) for c in js["candidates"] if c["Party"] == "Dem"), None)
                rpc = next((num(c["Percent"]) for c in js["candidates"] if c["Party"] == "Rep"), None)
                if dpc is not None and rpc is not None:
                    alt_m, alt_src = dpc - rpc, "CA SoS API " + js.get("ReportingTime", "")
        elif st in sections:
            ib = parse_infobox(sections[st].get(d, ""))
            if ib:
                dpc = next((n["pct"] for n in ib["noms"] if n["party"] == "D"), None)
                rpc = next((n["pct"] for n in ib["noms"] if n["party"] == "R"), None)
                if dpc is not None and rpc is not None:
                    alt_m, alt_src = dpc - rpc, "Wikipedia infobox"
        else:
            have_alt = False
        if have_alt and alt_m is None and mr is not None:
            dems = [c for c in mr["cands"] if c["party"].startswith(("Democratic", "DFL"))]
            reps = [c for c in mr["cands"] if c["party"].startswith("Republican")]
            if len(dems) == 1 and len(reps) == 1 and dems[0]["pct"] is not None and reps[0]["pct"] is not None:
                alt_m, alt_src = dems[0]["pct"] - reps[0]["pct"], "Wikipedia national page"
        if have_alt:
            rec["alt_dem_margin"] = None if alt_m is None else round(alt_m, 2)
            rec["alt_source"] = alt_src
        else:
            rec["alt_dem_margin"], rec["alt_source"] = old.get("alt_dem_margin"), old.get("alt_source", "")
            alt_m = to_float(rec["alt_dem_margin"])
        rec["dem_margin"] = to_float(rec["dem_margin"])
        if rec["dem_margin"] is None and alt_m is not None:  # fall back when NBC lacks the race
            rec["dem_margin"], rec["results_source"] = round(alt_m, 2), alt_src
        # winner: NBC/AP call first, then the national Wikipedia page's check mark; blank = uncalled
        if wiki_winner is None:
            wiki_winner = old.get("winner_party", "") if not rec["nbc_winner_party"] else ""
        rec["winner_party"] = rec["nbc_winner_party"] or wiki_winner
        rec["source_disagree"] = int(rec["dem_margin"] is not None and alt_m is not None and abs(rec["dem_margin"] - alt_m) > 1.0)

        h, t, m24 = pres.get((st, d), (None, None, None))
        rec["harris24"], rec["trump24"], rec["pres24_margin"] = h, t, m24
        rec["pres24_source"] = "The Downballot (2026 lines)" if m24 is not None else ""
        rec["redrawn_2026"] = int(st in REDRAWN)
        rec["pres24_from_memory"] = 0
        hs, ba = acs.get(FIPS[st] + ("00" if d == 0 else f"{d:02d}"), (None, None))
        if st in REDRAWN:
            hs = ba = None
        rec["hisp_share_acs24"], rec["ba_plus_share_acs24"] = hs, ba
        rec["overperf"] = round(rec["dem_margin"] - m24, 2) if rec["dem_margin"] is not None and m24 is not None else None
        for c in ("incumbency", "jd_endorsed", "dsa_endorsed", "sanders_endorsed", "ourrev_endorsed", "cpcpac_endorsed",
                  "newdem_endorsed", "bluedog_endorsed", "welcome_endorsed", "endorse_lines_found", "endorse_source",
                  "cpc_member", "newdem_member", "bluedog_member", "faction_sources"):
            rec[c] = s[c]
        row = {c: fmt_pandas(v, kind(c)) for c, v in rec.items()}
        row.update(derived(row))
        rows.append({c: fmt_pandas(row[c], kind(c)) for c in HOUSE})
    return rows


def derived(r):
    """Derived columns from analyze.py's load(): faction groupings, competitiveness, flips."""
    def flag(cols):
        return max(int(to_float(r[c]) or 0) for c in cols)
    out = {"contested_ok": True, "d_inc": int(r["incumbency"] == "D_inc"), "r_inc": int(r["incumbency"] == "R_inc")}
    out["prog"] = flag(["cpc_member", "jd_endorsed", "dsa_endorsed", "sanders_endorsed", "ourrev_endorsed", "cpcpac_endorsed"])
    out["mod"] = flag(["newdem_member", "newdem_endorsed", "bluedog_member", "bluedog_endorsed", "welcome_endorsed"])
    out["prog_strict"] = flag(["jd_endorsed", "dsa_endorsed", "sanders_endorsed"])
    out["mod_strict"] = flag(["bluedog_member", "bluedog_endorsed", "welcome_endorsed"])
    out["prog_member"] = flag(["cpc_member"])
    out["mod_member"] = flag(["newdem_member", "bluedog_member"])
    for p, m, name in (("prog", "mod", "faction"), ("prog_strict", "mod_strict", "faction_strict"),
                       ("prog_member", "mod_member", "faction_member")):
        pv, mv = out[p], out[m]
        out[name] = ("progressive" if pv and not mv else "moderate" if mv and not pv else "both" if pv and mv else "unflagged")
        out[p + "_only"] = int(pv == 1 and mv == 0)
        out[m + "_only"] = int(mv == 1 and pv == 0)
        out[p + "_" + m + "_both"] = int(pv == 1 and mv == 1)
    pm = to_float(r["pres24_margin"])
    out["competitive"] = pm is not None and abs(pm) <= 15
    out["flip"] = int(r["winner_party"] == "D" and r["prior_party"] == "R")
    out["d_win_trump_seat"] = int(r["winner_party"] == "D" and pm is not None and pm < 0)
    return out
