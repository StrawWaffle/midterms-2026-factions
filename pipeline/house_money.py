"""House general-election money: public/data/house_money_2026.csv.

Port of the research scripts house_money/scripts/{ielib,assign,build_house_money}.py and the
data-producing part of analyze_money.py. Fetched each run: the FEC 2026 bulk files (weball26,
independent_expenditure_2026.csv, pas226). Static inputs in static/house_money/: nominee_fec_ids.csv
(nominee-to-FEC-candidate matches from match_nominees.py), dccc_red_to_blue.csv, dccc_frontline.csv and
house_ratings_final.csv. Seat-level results come from the House dataset built in the same run.
"""
import collections
import re
import unicodedata
from datetime import datetime

import fec
from common import STATIC, Guard, fmt_pandas, read_csv, to_float
from schema import HOUSE_MONEY, HOUSE_MONEY_BOOL, HOUSE_MONEY_FLOAT

S = STATIC / "house_money"
HMP = {"C00495028": "House Majority PAC", "C00744920": "CFFE PAC (shares HMP address; connected org Caregivers House Victory Fund)"}
DCCC, NRCC = "C00000935", "C00075820"
PROG_CORE = {"C00630665": "Justice Democrats PAC", "C00513176": "Congressional Progressive Caucus PAC",
             "C00606962": "Working Families Party PAC"}
PROG_CORE_NAMES = ["JUSTICE DEMOCRATS", "CONGRESSIONAL PROGRESSIVE CAUCUS", "WORKING FAMILIES PARTY", "OUR REVOLUTION",
                   "DEMOCRATIC SOCIALISTS", "PROGRESSIVE CHANGE CAMPAIGN", "FIGHTING OLIGARCHY"]
PROG_BROAD = {"C00897926": "Progressive Promise", "C00341396": "MoveOn", "C00678839": "Indivisible Action",
              "C90017492": "Indivisible Project", "C00843110": "Leaders We Deserve", "C00879080": "Citizens Against AIPAC Corruption",
              "C00685552": "Medicare For All", "C00736009": "Popular Democracy PAC"}
PROG_BROAD_NAMES = ["SUNRISE", "MOVEON", "INDIVISIBLE"]
MOD_CORE = {"C00859660": "New Democrat Majority", "C00786830": "WelcomePAC"}
MOD_CORE_NAMES = ["NEW DEMOCRAT", "NEWDEM", "BLUE DOG", "WELCOMEPAC", "MAJORITY DEMOCRATS"]
MOD_BROAD = {"C00710848": "DMFI PAC", "C00568444": "Center Forward Committee", "C00875450": "Center Forward Initiative"}
MOD_BROAD_NAMES = ["MAINSTREAM DEMOCRATS"]
CLF = {"C00504530"}
AIPAC = {"C00799031"}  # United Democracy Project
AIPAC_NAMES = ["UNITED DEMOCRACY PROJECT", "AIPAC PAC"]
CRYPTO = {"C00835959": "Fairshake", "C00836221": "Defend American Jobs", "C00848440": "Protect Progress"}
FEC_COLS = HOUSE_MONEY[:48]


def kind(col):
    if col in HOUSE_MONEY_FLOAT:
        return "float"
    if col in HOUSE_MONEY_BOOL:
        return "bool"
    return "int" if col in ("total_votes", "red_to_blue", "frontline", "dem_won", "challenger_or_open", "flag_prog", "flag_mod") else "str"


# ---------------------------------------------------------------- ielib.py / match_nominees.py / assign.py
def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z ]", " ", s)


SUFFIX = {"JR", "SR", "II", "III", "IV", "MD", "DR", "MR", "MS", "MRS", "PHD"}


def lastname(full):
    toks = [t for t in norm(full).split() if t not in SUFFIX]
    return toks[-1] if toks else ""


def fec_tokens(fecname):
    last, _, first = fecname.partition(",")
    return set(norm(last).split()), set(norm(first).split())


def pdate(s, f="%d-%b-%y"):
    try:
        return datetime.strptime(s, f)
    except Exception:  # noqa: BLE001
        return None


def load_weball(paths):
    cols = ("CAND_ID CAND_NAME CAND_ICI PTY_CD PTY TTL_RECEIPTS TRANS_FROM_AUTH TTL_DISB TRANS_TO_AUTH COH_BOP COH_COP "
            "CAND_CONTRIB CAND_LOANS OTHER_LOANS CAND_LOAN_REPAY OTHER_LOAN_REPAY DEBTS TTL_INDIV ST DIST SPEC PRIM RUN GEN GENPCT "
            "OTHER_POL_CMTE POL_PTY CVG_END INDIV_REFUNDS CMTE_REFUNDS").split()
    out = {}
    for l in fec.lines(paths, "weball26"):
        d = dict(zip(cols, l.rstrip("\n").split("|")))
        out[d["CAND_ID"]] = d
    return out


def load_ie(paths, office="H"):
    """House IEs, one row per (spender, transaction id) keeping the latest filing; drops single rows over $25M."""
    rows = [r for r in fec.ie_rows(paths, "latin-1") if r["can_office"] == office]
    best = {}
    for r in rows:
        try:
            r["amt"] = float(r["exp_amo"])
        except Exception:  # noqa: BLE001
            r["amt"] = 0.0
        k = (r["spe_id"], r["tran_id"])
        fn = int(r["file_num"] or 0)
        if k not in best or fn > int(best[k]["file_num"] or 0):
            best[k] = r
    out = [r for r in best.values() if abs(r["amt"]) < 25e6]
    for r in out:
        r["date"] = pdate(r["exp_date"]) or pdate(r["dissem_dt"]) or pdate(r["receipt_dat"])
    return out


def load_pas2(paths):
    cols = ("CMTE_ID AMNDT_IND RPT_TP TRANSACTION_PGI IMAGE_NUM TRANSACTION_TP ENTITY_TP NAME CITY STATE ZIP_CODE EMPLOYER "
            "OCCUPATION TRANSACTION_DT TRANSACTION_AMT OTHER_ID CAND_ID TRAN_ID FILE_NUM MEMO_CD MEMO_TEXT SUB_ID").split()
    for l in fec.lines(paths, "pas226"):
        f = l.rstrip("\n").split("|")
        if f[0] not in (DCCC, NRCC):  # only the two party committees are used
            continue
        d = dict(zip(cols, f))
        try:
            d["amt"] = float(d["TRANSACTION_AMT"])
        except Exception:  # noqa: BLE001
            d["amt"] = 0.0
        d["date"] = pdate(d["TRANSACTION_DT"], "%m%d%Y")
        yield d


def build_index(id_rows, seats):
    ids, byname = {}, {}
    for r in id_rows:
        s = seats[r["code"]]
        for side, nom in (("D", s["dem_nominee"]), ("R", s["rep_nominee"])):
            cid = r["dem_cand_id" if side == "D" else "rep_cand_id"]
            if cid:
                ids[cid] = (r["code"], side)
            byname.setdefault((s["state"], lastname(nom)), []).append((r["code"], side))
    return ids, byname


def assign(r, ids, byname):
    if r["cand_id"] in ids:
        return ids[r["cand_id"]]
    st = r["can_office_state"]
    lasts, firsts = fec_tokens(r["cand_name"]) if "," in r["cand_name"] else (set(norm(r["cand_name"]).split()), set())
    hits = set()
    for t in lasts | firsts:
        for h in byname.get((st, t), []):
            hits.add(h)
    if len(hits) > 1 and r["can_office_dis"]:
        d = r["can_office_dis"].zfill(2)
        hits = {h for h in hits if h[0].split("-")[1].replace("AL", "00").zfill(2) == d} or hits
    if len(hits) == 1:
        return hits.pop()
    return None


def direction(r, side):
    """+1 = helps the Democrat (support D / oppose R); -1 = hurts the Democrat."""
    so = r["sup_opp"].upper()[:1]
    if so not in ("S", "O"):
        return 0
    return (1 if so == "S" else -1) * (1 if side == "D" else -1)


def pro_class(sid, name):
    n = name.upper()
    if sid in HMP:
        return "a_estab"
    if sid in PROG_CORE or any(p in n for p in PROG_CORE_NAMES):
        return "b_prog_core"
    if sid in MOD_CORE or any(p in n for p in MOD_CORE_NAMES):
        return "c_mod_core"
    if sid in PROG_BROAD or any(p in n for p in PROG_BROAD_NAMES):
        return "b2_prog_broad"
    if sid in MOD_BROAD or any(p in n for p in MOD_BROAD_NAMES):
        return "c2_mod_broad"
    if sid in CRYPTO:
        return "d_crypto"
    return "d_other"


def anti_class(sid, name):
    n = name.upper()
    if sid in CLF:
        return "clf"
    if sid in AIPAC or any(p in n for p in AIPAC_NAMES):
        return "aipac_udp"
    if sid in CRYPTO:
        return "crypto"
    return "other"


def f(x):
    try:
        return float(x)
    except Exception:  # noqa: BLE001
        return 0.0


# ---------------------------------------------------------------- build_house_money.py
GUARDED = (["dem_receipts", "dem_disbursements", "dem_indiv_contrib", "dem_cand_self_funding", "rep_receipts"]
           + [c for c in FEC_COLS if c.startswith(("ie_", "dccc_", "nrcc_"))])


def build_fec(seats_list, paths, guard):
    seats = {s["code"]: s for s in seats_list}
    id_list = read_csv(S / "nominee_fec_ids.csv")
    ids_rows = {r["code"]: r for r in id_list}
    ids, byname = build_index(id_list, seats)
    bydist = {}
    for s in seats_list:
        st, d = s["code"].split("-")
        bydist[(st, "00" if d == "AL" else d)] = s["code"]
    wb = load_weball(paths)
    ie = load_ie(paths)

    acc = collections.defaultdict(lambda: collections.defaultdict(float))
    first = {}
    for r in ie:
        if r["ele_type"] != "G":
            continue
        dis = r["can_office_dis"].strip().zfill(2) if r["can_office_dis"].strip() else ""
        if r["cand_id"] in ids:
            a = ids[r["cand_id"]]
        else:
            a = assign(r, ids, byname)
            if a and dis and a[0].split("-")[1].replace("AL", "00") != dis:
                a = None
            if not a and dis and (r["can_office_state"], dis) in bydist and r["cand_pty_aff"][:3] in ("DEM", "REP"):
                # G-labelled spending about a non-nominee major-party candidate in a D-vs-R seat (e.g. a withdrawn incumbent)
                a = (bydist[(r["can_office_state"], dis)], "D" if r["cand_pty_aff"].startswith("DEM") else "R")
        if not a:
            continue
        code, side = a
        d = direction(r, side)
        if d == 0:
            continue
        sid = r["spe_id"]
        late = bool(r["date"] and r["date"].strftime("%Y-%m-%d") >= "2026-10-15")
        if d > 0:
            c = pro_class(sid, r["spe_nam"])
            acc[code]["ie_pro_" + c] += r["amt"]
            acc[code]["ie_pro_total"] += r["amt"]
            if late:
                acc[code]["ie_pro_total_after_oct14"] += r["amt"]
                if c == "a_estab":
                    acc[code]["ie_pro_a_estab_after_oct14"] += r["amt"]
            if c == "a_estab" and r["date"]:
                k = code + "hmp"
                if k not in first or r["date"] < first[k]:
                    first[k] = r["date"]
        else:
            c = anti_class(sid, r["spe_nam"])
            acc[code]["ie_anti_" + c] += r["amt"]
            acc[code]["ie_anti_total"] += r["amt"]

    # party coordinated expenditures (24C) and direct party contributions (24K/24Z), from regular reports
    cand2seat = {}
    for code, r in ids_rows.items():
        if r["dem_cand_id"]:
            cand2seat[r["dem_cand_id"]] = (code, "D")
        if r["rep_cand_id"]:
            cand2seat[r["rep_cand_id"]] = (code, "R")
    for p in load_pas2(paths):
        who = "dccc" if p["CMTE_ID"] == DCCC else "nrcc"
        if p["CAND_ID"] not in cand2seat:
            continue
        code, side = cand2seat[p["CAND_ID"]]
        sfx = "dem" if side == "D" else "rep"
        if p["TRANSACTION_TP"] == "24C":
            acc[code][who + "_coord_" + sfx] += p["amt"]
        elif p["TRANSACTION_TP"] in ("24K", "24Z"):
            acc[code][who + "_contrib_" + sfx] += p["amt"]

    res = []
    for s in seats_list:
        code = s["code"]
        a = acc[code]
        idr = ids_rows[code]
        dw = wb.get(idr["dem_cand_id"], {})
        rw = wb.get(idr["rep_cand_id"], {})
        row = {k: s[k] for k in ["code", "dem_nominee", "rep_nominee", "faction", "incumbency", "pres24_margin", "dem_margin", "overperf", "total_votes"]}
        row.update(dem_cand_id=idr["dem_cand_id"], dem_receipts=f(dw.get("TTL_RECEIPTS")), dem_disbursements=f(dw.get("TTL_DISB")),
                   dem_cash_on_hand=f(dw.get("COH_COP")), dem_indiv_contrib=f(dw.get("TTL_INDIV")),
                   dem_cand_self_funding=f(dw.get("CAND_CONTRIB")) + f(dw.get("CAND_LOANS")), dem_cvg_end=dw.get("CVG_END", ""),
                   rep_cand_id=idr["rep_cand_id"], rep_receipts=f(rw.get("TTL_RECEIPTS")), rep_cash_on_hand=f(rw.get("COH_COP")),
                   rep_cvg_end=rw.get("CVG_END", ""))
        for k in FEC_COLS:
            if k.startswith(("ie_", "dccc_", "nrcc_")):
                row[k] = round(a.get(k, 0.0), 2)
        for c in GUARDED:
            row[c] = guard.check(code, c, row[c], s["rep_nominee"] if c.startswith(("rep_", "nrcc_")) else s["dem_nominee"])
        for side, cvg in (("dem", "dem_cvg_end"), ("rep", "rep_cvg_end")):
            row.update(guard.keep_with(code, f"{side}_receipts", [f"{side}_cash_on_hand", cvg]))
        row["estab_total"] = round(row["ie_pro_a_estab"] + row["dccc_coord_dem"], 2)
        row["pro_dem_outside_total"] = round(row["ie_pro_total"] + row["dccc_coord_dem"], 2)
        row["anti_dem_outside_total"] = round(row["ie_anti_total"] + row["nrcc_coord_rep"], 2)
        row["hmp_first_ie_date"] = first[code + "hmp"].strftime("%Y-%m-%d") if code + "hmp" in first else ""
        tv = f(s["total_votes"])
        for num, name in [("estab_total", "estab_per_voter"), ("pro_dem_outside_total", "pro_dem_outside_per_voter"),
                          ("anti_dem_outside_total", "anti_dem_outside_per_voter"), ("dem_receipts", "dem_receipts_per_voter"),
                          ("rep_receipts", "rep_receipts_per_voter")]:
            row[name] = round(row[num] / tv, 3) if tv else ""
        row["net_outside_per_voter"] = round(row["pro_dem_outside_per_voter"] - row["anti_dem_outside_per_voter"], 3) if tv else ""
        # the research build wrote this with csv and re-read it with pandas
        res.append({k: fmt_pandas(to_float(row[k]) if kind(k) == "float" else row[k], kind(k)) for k in FEC_COLS})
    return res


# ---------------------------------------------------------------- analyze_money.py (data part)
def norm_code(c):
    c = str(c).strip().upper().replace("–", "-")
    if "-" not in c:
        return c
    st, d = c.split("-", 1)
    if d in ("AL", "00", "0", "AT-LARGE"):
        return st + "-AL"
    return f"{st}-{int(d):02d}" if d.isdigit() else c


def first_by_code(rows, sort_key=None):
    """pandas sort_values(...).groupby('code').first(): first non-empty value per column within each code."""
    if sort_key:
        rows = sorted(rows, key=lambda r: r[sort_key])
    out = {}
    for r in rows:
        o = out.setdefault(r["code"], {})
        for k, v in r.items():
            if v != "" and k not in o:
                o[k] = v
    return out


def bucket(s):
    s = str(s).lower()
    if "toss" in s or "tilt" in s:
        return "Toss-up"
    if "lean" in s:
        return "Lean"
    if "likely" in s:
        return "Likely"
    return ""


def lean_bin(x):
    """pd.cut(pres24_margin, [-100, -15, -10, -5, 0, 5, 15, 100]) with right-closed bins."""
    if x is None:
        return ""
    for hi, label in ((-15, "<R+15"), (-10, "R+10-15"), (-5, "R+5-10"), (0, "R+0-5"), (5, "D+0-5"), (15, "D+5-15"), (100, ">D+15")):
        if -100 < x <= hi:
            return label
    return ""


def build(house_rows, paths, prev_rows=()):
    m = build_fec(house_rows, paths, Guard("house_money_2026.csv", prev_rows))

    def load(name):
        rows = read_csv(S / name)
        for r in rows:
            r["code"] = norm_code(r["code"])
        return rows
    rtb, fl, rt = load("dccc_red_to_blue.csv"), load("dccc_frontline.csv"), load("house_ratings_final.csv")
    nom = {r["code"]: r["dem_nominee"] for r in m}

    def is_nominee(row):
        n = str(nom.get(row["code"], "")).lower()
        last = str(row["candidate"]).replace(" J.", "").split()[-1].lower()
        return last in n
    for r in rtb:
        r.setdefault("tier", "red_to_blue")
        r["is_nominee"] = is_nominee(r)
    is_red = lambda r: "red" in (r["tier"] or "nan").lower()  # noqa: E731
    lost = first_by_code([r for r in rtb if not r["is_nominee"] and is_red(r)])
    r2b = first_by_code([r for r in rtb if r["is_nominee"] and is_red(r)], "date_added")
    em = first_by_code([r for r in rtb if r["is_nominee"] and not is_red(r)], "date_added")
    f1 = first_by_code(fl, "date_added")
    rtg = first_by_code(rt)

    out = []
    for r in m:
        code = r["code"]
        r["red_to_blue_primary_pick_lost"] = lost.get(code, {}).get("candidate", "")
        r["red_to_blue"] = int(code in r2b)
        r["red_to_blue_date"] = r2b.get(code, {}).get("date_added", "")
        r["dccc_emerging_or_other_tier"] = em.get(code, {}).get("tier", "")
        r["dccc_emerging_date"] = em.get(code, {}).get("date_added", "")
        r["frontline"] = int(code in f1)
        r["frontline_date"] = f1.get(code, {}).get("date_added", "")
        for c in ("cook_final", "sabato_final", "inside_final"):
            r[c] = rtg.get(code, {}).get(c, "")
        r["rating_source"] = rtg.get(code, {}).get("source_url", "")
        rb = ""
        for c in ("cook_final", "inside_final", "sabato_final"):
            rb = rb or bucket(r[c] if r[c] != "" else "nan")
        r["rating_bucket"] = rb
        r["rating_source_used"] = "Cook" if bucket(r["cook_final"] or "nan") != "" else ("Inside/Sabato" if rb != "" else "")
        pm, dm = to_float(r["pres24_margin"]), to_float(r["dem_margin"])
        r["in_competitive_set"] = (rb != "" or (pm is not None and abs(pm) <= 15)) and code != "AK-AL"
        r["faction2"] = r["faction"]
        r["dem_won"] = int(dm is not None and dm > 0)
        r["lean_bin"] = lean_bin(pm)
        r["challenger_or_open"] = int(r["incumbency"] != "D_inc")
        r["flag_prog"] = int(r["faction"] in ("progressive", "both"))
        r["flag_mod"] = int(r["faction"] in ("moderate", "both"))
        out.append({c: fmt_pandas(r[c], kind(c)) for c in HOUSE_MONEY})
    return out
