"""Build the static page (site/index.html) and copy the datasets next to it.

    python -I build.py

Standard library only. Charts are inline SVG generated from data/*.csv.
"""

import csv
import hashlib
import html
import math
import re
import shutil
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"

W = 720            # chart viewBox width
ML, MR = 150, 24   # left/right margins for row charts

FACTION = {
    "moderate": ("Moderate", "var(--moderate)", "circle"),
    "progressive": ("Progressive", "var(--progressive)", "square"),
    "both": ("Both flags", "var(--both)", "diamond"),
    "unflagged": ("No flag", "var(--neutral)", "circle-open"),
    "mixed-unclear": ("Mixed or unclear", "var(--neutral)", "circle-open"),
}


def esc(s):
    return html.escape(str(s), quote=True)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def jitter(key, spread):
    h = int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return (h - 0.5) * 2 * spread


def mark(shape, x, y, color, tip, r=4.2):
    t = f' data-tip="{esc(tip)}" tabindex="0"' if tip else ""
    if shape == "square":
        s = r * 1.7
        return f'<rect x="{x - s / 2:.1f}" y="{y - s / 2:.1f}" width="{s:.1f}" height="{s:.1f}" fill="{color}" class="mk"{t}/>'
    if shape == "diamond":
        s = r * 1.35
        return (f'<path d="M{x:.1f} {y - s:.1f}L{x + s:.1f} {y:.1f}L{x:.1f} {y + s:.1f}L{x - s:.1f} {y:.1f}Z" '
                f'fill="{color}" class="mk"{t}/>')
    if shape == "circle-open":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r - 0.8:.1f}" fill="none" style="stroke:{color};stroke-width:1.6" class="mk"{t}/>'
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}" class="mk"{t}/>'


def legend(keys):
    items = []
    for k in keys:
        label, color, shape = FACTION[k]
        items.append(f'<span class="lg"><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">'
                     f'{mark(shape, 7, 7, color, None, 4.6)}</svg>{esc(label)}</span>')
    return f'<div class="legend">{"".join(items)}</div>'


def scale(d0, d1, r0, r1):
    return lambda v: r0 + (v - d0) / (d1 - d0) * (r1 - r0)


def ticks(lo, hi, step):
    v = math.ceil(lo / step) * step
    out = []
    while v <= hi + 1e-9:
        out.append(round(v, 6))
        v += step
    return out


def signed(v, digits=1):
    return f"{v:+.{digits}f}".replace("-", "−")


def x_axis(sx, lo, hi, step, y0, y1, fmt=signed, label=None):
    parts = []
    for t in ticks(lo, hi, step):
        x = sx(t)
        cls = "zero" if t == 0 else "grid"
        parts.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y0}" y2="{y1}" class="{cls}"/>')
        parts.append(f'<text x="{x:.1f}" y="{y1 + 16}" class="tick" text-anchor="middle">{fmt(t, 0) if fmt is signed else fmt(t)}</text>')
    if label:
        parts.append(f'<text x="{(sx(lo) + sx(hi)) / 2:.1f}" y="{y1 + 34}" class="axis-label" text-anchor="middle">{esc(label)}</text>')
    return "".join(parts)


def svg(height, body, title, desc):
    # aria-label instead of a <title> child: browsers show <title> as a native hover tooltip
    # over the whole chart, which covers the page's own tooltip.
    did = f"d-{hashlib.sha1(desc.encode()).hexdigest()[:8]}"
    return (f'<svg viewBox="0 0 {W} {height}" role="img" aria-label="{esc(title)}" aria-describedby="{did}">'
            f'<desc id="{did}">{esc(desc)}</desc>{body}</svg>')


# ---------------------------------------------------------------- data

def load():
    house = list(csv.DictReader(open(HERE / "data/house_2026.csv", encoding="utf-8")))
    state = list(csv.DictReader(open(HERE / "data/statewide_2026.csv", encoding="utf-8")))
    for r in house:
        for k in ("dem_margin", "pres24_margin", "overperf", "hisp_share_acs24"):
            r[k] = num(r[k])
    state = [r for r in state if r["dem_type"] == "Democrat" and num(r["swing_vs_2024"]) is not None
             and r["faction"] in ("moderate", "progressive", "mixed-unclear")]
    for r in state:
        for k in ("dem_margin", "pres2024_margin", "swing_vs_2024", "dem_pct"):
            r[k] = num(r[k])
    return house, state


# ---------------------------------------------------------------- charts

ROWS = ["moderate", "both", "progressive", "unflagged"]


def strip_chart(house, field, lo, hi, step, axis_label, title, desc, band=None, tipfmt=None):
    row_h, top = 62, 26
    h = top + row_h * len(ROWS) + 48
    sx = scale(lo, hi, ML, W - MR)
    body = []
    if band:
        body.append(f'<rect x="{sx(band[0]):.1f}" y="{top}" width="{sx(band[1]) - sx(band[0]):.1f}" '
                    f'height="{row_h * len(ROWS)}" class="band"/>')
        body.append(f'<text x="{(sx(band[0]) + sx(band[1])) / 2:.1f}" y="{top - 8}" class="note" text-anchor="middle">{esc(band[2])}</text>')
    body.append(x_axis(sx, lo, hi, step, top, top + row_h * len(ROWS), label=axis_label))
    for i, f in enumerate(ROWS):
        label, color, shape = FACTION[f]
        rows = [r for r in house if r["faction"] == f and r[field] is not None]
        vals = [r[field] for r in rows]
        cy = top + row_h * i + row_h / 2
        med = st.median(vals)
        body.append(f'<text x="{ML - 12}" y="{cy - 4:.1f}" class="row-label" text-anchor="end">{esc(label)}</text>')
        body.append(f'<text x="{ML - 12}" y="{cy + 12:.1f}" class="row-sub" text-anchor="end">'
                    f'n={len(vals)}, median {signed(med)}</text>')
        for r in rows:
            v = min(max(r[field], lo), hi)
            tip = tipfmt(r) if tipfmt else None
            body.append(mark(shape, sx(v), cy + jitter(r["code"], row_h * 0.32), color, tip, 3.4))
        body.append(f'<line x1="{sx(med):.1f}" x2="{sx(med):.1f}" y1="{cy - row_h * 0.42:.1f}" y2="{cy + row_h * 0.42:.1f}" class="median"/>')
    return svg(h, "".join(body), title, desc)


def house_tip(r):
    return (f"{r['code']}: {r['dem_nominee']} (D) vs {r['rep_nominee']} (R). "
            f"2026 margin {signed(r['dem_margin'])}, 2024 presidential {signed(r['pres24_margin'])}, "
            f"ran {signed(r['overperf'])} ahead of Harris")


def flips_chart(house):
    flips = sorted([r for r in house if r["prior_party"] == "R" and r["winner_party"] == "D"],
                   key=lambda r: r["dem_margin"])
    lo, hi = 0, 40
    top, cell = 16, 11
    stacks = {}
    pts = []
    for r in flips:
        b = int(r["dem_margin"])  # 1-point bins
        k = stacks.get(b, 0)
        stacks[b] = k + 1
        pts.append((r, b, k))
    maxk = max(stacks.values())
    base = top + 36 + cell * maxk
    h = base + 52
    sx = scale(lo, hi, 40, W - MR)
    body = [f'<rect x="{sx(0):.1f}" y="{top}" width="{sx(3) - sx(0):.1f}" height="{base - top}" class="band strong"/>',
            f'<text x="{sx(3) + 6:.1f}" y="{top + 12}" class="note">Won by under 3 points: '
            f'{sum(1 for r in flips if r["dem_margin"] < 3)} of {len(flips)}</text>',
            x_axis(sx, lo, hi, 5, top, base, fmt=lambda t: f"+{t:.0f}" if t else "0",
                   label="Democratic winning margin in flipped seats (points)")]
    for r, b, k in pts:
        label, color, shape = FACTION[r["faction"]]
        x = sx(b + 0.5)
        y = base - cell / 2 - k * cell - 1
        body.append(mark(shape, x, y, color, f"{r['code']}: {r['dem_nominee']} won by {r['dem_margin']:.1f} ({label.lower()})", 4.4))
    return svg(h, "".join(body), "Margins in the 42 seats Democrats flipped",
               "Dot histogram of the 42 flipped House seats by Democratic winning margin, one dot per seat, "
               "with seats won by under 3 points highlighted."), flips


def scatter_state(state):
    lo_x, hi_x, lo_y, hi_y = -50, 35, -12, 32
    top, left, bottom = 14, 52, 50
    h = 520
    sx = scale(lo_x, hi_x, left, W - MR)
    sy = scale(lo_y, hi_y, h - bottom, top)
    body = []
    for t in ticks(lo_y, hi_y, 10):
        body.append(f'<line x1="{left}" x2="{W - MR}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="{"zero" if t == 0 else "grid"}"/>')
        body.append(f'<text x="{left - 8}" y="{sy(t) + 4:.1f}" class="tick" text-anchor="end">{signed(t, 0)}</text>')
    body.append(x_axis(sx, lo_x, hi_x, 10, top, h - bottom, label="2024 presidential margin in the state (Harris minus Trump)"))
    body.append(f'<text x="{left - 40}" y="{top - 2}" class="axis-label">Swing</text>')
    xs = [r["pres2024_margin"] for r in state]
    ys = [r["swing_vs_2024"] for r in state]
    mx, my = st.mean(xs), st.mean(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    icpt = my - slope * mx
    body.append(f'<line x1="{sx(lo_x):.1f}" y1="{sy(icpt + slope * lo_x):.1f}" x2="{sx(hi_x):.1f}" '
                f'y2="{sy(icpt + slope * hi_x):.1f}" class="fit"/>')
    order = {"mixed-unclear": 0, "moderate": 1, "progressive": 2}
    labels = {
        "Abdul El-Sayed": (-8, 4, "end"), "Peggy Flanagan": (8, 10, "start"), "Troy Jackson": (8, 4, "start"),
        "Roy Cooper": (9, 4, "start"), "James Talarico": (0, -10, "middle"), "Adam Hamilton": (-8, 4, "end"),
        "Annie Andrews": (-9, -4, "end"), "Josh Turek": (-9, 4, "end"), "Amanda Janoo": (-8, -8, "end"),
        "Jocelyn Benson": (-8, -6, "end"), "Amy Klobuchar": (8, -2, "start"),
    }
    for r in sorted(state, key=lambda r: order[r["faction"]]):
        label, color, shape = FACTION[r["faction"]]
        x, y = sx(r["pres2024_margin"]), sy(max(r["swing_vs_2024"], lo_y + 1))
        tip = (f"{r['st']} {r['office']}: {r['dem_nominee']} ({label.lower()}). Margin {signed(r['dem_margin'])}, "
               f"2024 presidential {signed(r['pres2024_margin'])}, swing {signed(r['swing_vs_2024'])}")
        body.append(mark(shape, x, y, color, tip, 4.6))
        if r["dem_nominee"] in labels:
            dx, dy, anchor = labels[r["dem_nominee"]]
            name = r["dem_nominee"].split()[-1] + (" (Gov)" if r["office"] == "Governor" else "")
            if r["swing_vs_2024"] < lo_y:
                name += f" (VT, {signed(r['swing_vs_2024'])}, off scale)"
            body.append(f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" class="point-label" text-anchor="{anchor}">{esc(name)}</text>')
    return svg(h, "".join(body), "Statewide swing against 2024 presidential margin",
               "Scatterplot of 65 Senate and governor races: x is the 2024 presidential margin in the state, "
               "y is the Democrat's swing from it, colored by faction, with a fitted line."), slope


def dumbbell(state):
    by = {}
    for r in state:
        by.setdefault(r["st"], {})["Senate" if r["office"].startswith("Senate") else r["office"]] = r
    pairs = []
    for s, d in by.items():
        if "Senate" in d and "Governor" in d:
            a, b = d["Senate"], d["Governor"]
            f = {a["faction"], b["faction"]}
            if f == {"progressive", "moderate"}:
                p, m = (a, b) if a["faction"] == "progressive" else (b, a)
                pairs.append((p, m))
    pairs.sort(key=lambda pm: pm[0]["dem_margin"] - pm[1]["dem_margin"])
    lo, hi = -5, 35
    top, row = 18, 40
    h = top + row * len(pairs) + 46
    left = 170
    sx = scale(lo, hi, left, W - 90)
    body = [x_axis(sx, lo, hi, 5, top, top + row * len(pairs), label="Democratic margin in the state, same ballot (points)")]
    rows = []
    for i, (p, m) in enumerate(pairs):
        cy = top + row * i + row / 2
        d = p["dem_margin"] - m["dem_margin"]
        body.append(f'<text x="{left - 12}" y="{cy - 3:.1f}" class="row-label" text-anchor="end">{esc(p["state"])}</text>')
        body.append(f'<text x="{left - 12}" y="{cy + 12:.1f}" class="row-sub" text-anchor="end">'
                    f'{esc(p["dem_nominee"].split()[-1])} vs {esc(m["dem_nominee"].split()[-1])}</text>')
        body.append(f'<line x1="{sx(p["dem_margin"]):.1f}" x2="{sx(m["dem_margin"]):.1f}" y1="{cy:.1f}" y2="{cy:.1f}" class="connector"/>')
        for r in (m, p):
            label, color, shape = FACTION[r["faction"]]
            body.append(mark(shape, sx(r["dem_margin"]), cy, color,
                             f"{r['dem_nominee']} ({r['office']}, {label.lower()}): {signed(r['dem_margin'])}", 5))
        body.append(f'<text x="{W - 8}" y="{cy + 4:.1f}" class="value" text-anchor="end">{signed(d)}</text>')
        rows.append((p, m, d))
    body.append(f'<text x="{W - 8}" y="{top + 2:.1f}" class="row-sub" text-anchor="end">difference</text>')
    return svg(h, "".join(body), "Same-ballot pairs: progressive and moderate Democrats in one state",
               "For seven states where one Democratic statewide nominee was progressive and the other moderate, "
               "each row shows both margins and the difference."), rows


def forest(rows):
    lo, hi = -8, 14
    top, row = 8, 30
    left = 330
    n = sum(1 + len(items) for _, items in rows)
    h = top + row * n + 46
    sx = scale(lo, hi, left, W - MR)
    body = []
    y = top
    gridtop = top
    for group, items in rows:
        body.append(f'<text x="8" y="{y + row * 0.65:.1f}" class="group-label">{esc(group)}</text>')
        y += row
        for label, est, ci, own, tip in items:
            cy = y + row / 2
            body.append(f'<text x="18" y="{cy + 4:.1f}" class="row-label-sm">{esc(label)}</text>')
            if ci:
                body.append(f'<line x1="{sx(max(ci[0], lo)):.1f}" x2="{sx(min(ci[1], hi)):.1f}" y1="{cy:.1f}" y2="{cy:.1f}" class="ci"/>')
            fill = "var(--ink)" if own else "var(--surface)"
            body.append(f'<circle cx="{sx(est):.1f}" cy="{cy:.1f}" r="5" fill="{fill}" style="stroke:var(--ink);stroke-width:1.6" '
                        f'class="mk" data-tip="{esc(tip)}" tabindex="0"/>')
            y += row
    body.insert(0, x_axis(sx, lo, hi, 2, gridtop, y, label="Moderate advantage, points of margin (left of 0: progressives did better)"))
    return svg(h, "".join(body), "Estimates of the moderate advantage",
               "Each row is one estimate of how many points of margin a moderate gains over a progressive; "
               "filled dots are this page's own estimates, hollow dots published ones; lines are ranges or 95% intervals.")


# ---------------------------------------------------------------- money charts

MONEY_FACTION = {"progressive": "progressive", "moderate": "moderate", "mixed-unclear": "mixed-unclear"}
RATING_ORDER = ["Tossup", "Lean D", "Likely D", "Lean R", "Likely R"]


def load_money():
    sen = [r for r in csv.DictReader(open(HERE / "data/senate_money_2026.csv", encoding="utf-8"))
           if r["office"].startswith("Senate") and r["cook_final"] in RATING_ORDER and r["faction"] in MONEY_FACTION]
    house = list(csv.DictReader(open(HERE / "data/house_money_2026.csv", encoding="utf-8")))
    return sen, house


def senate_money_chart(sen):
    rows = sorted(sen, key=lambda r: (RATING_ORDER.index(r["cook_final"]), -float(r["party_pro_dem_per_vap"])))
    lo, hi = 0, 90
    left, top, row, gap = 190, 22, 30, 22
    groups = []
    for r in rows:
        if not groups or groups[-1][0] != r["cook_final"]:
            groups.append((r["cook_final"], []))
        groups[-1][1].append(r)
    h = top + sum(gap + row * len(g) for _, g in groups) + 44
    sx = scale(lo, hi, left, W - 70)
    body = [f'<text x="{W - 8}" y="{top - 8}" class="row-sub" text-anchor="end">party share</text>']
    y = top
    plot_top = top
    out_rows = []
    for rating, items in groups:
        body.append(f'<text x="8" y="{y + 15:.1f}" class="group-label">{esc(rating)}</text>')
        y += gap
        for r in items:
            cy = y + row / 2
            party, against = float(r["party_pro_dem_per_vap"]), float(r["against_dem_total_per_vap"])
            label, color, shape = FACTION[MONEY_FACTION[r["faction"]]]
            body.append(f'<text x="18" y="{cy + 4:.1f}" class="row-label-sm">{esc(r["st"])} · {esc(r["democrat"])}</text>')
            body.append(f'<line x1="{sx(party):.1f}" x2="{sx(min(against, hi)):.1f}" y1="{cy:.1f}" y2="{cy:.1f}" class="connector thin"/>')
            ax = sx(min(against, hi))
            body.append(f'<line x1="{ax:.1f}" x2="{ax:.1f}" y1="{cy - 8:.1f}" y2="{cy + 8:.1f}" class="against"/>')
            body.append(f'<rect x="{ax - 6:.1f}" y="{cy - 10:.1f}" width="12" height="20" fill="transparent" '
                        f'data-tip="{esc(r["st"])}: ${against:.2f} per adult spent against {esc(r["democrat"])} by outside groups" tabindex="0"/>')
            body.append(mark(shape, sx(party), cy, color,
                             f"{r['st']}: ${party:.2f} per adult from the party network for {r['democrat']} ({label.lower()})", 4.8))
            share = f"{party / against * 100:.0f}%" if against > 0.05 else "n/a"
            body.append(f'<text x="{W - 8}" y="{cy + 4:.1f}" class="value" text-anchor="end">{share}</text>')
            out_rows.append((r, party, against, share))
            y += row
    body.insert(0, x_axis(sx, lo, hi, 10, plot_top, y, fmt=lambda t: f"${t:.0f}",
                          label="Outside money per adult in the state, general election (US dollars)"))
    return svg(h, "".join(body), "Party money for the Democrat against money spent against them, Senate 2026",
               "For each contested 2026 Senate race, a filled mark shows party-network spending for the Democrat per adult and "
               "a grey tick shows all outside spending against the Democrat per adult; the right column is the share matched."), out_rows


def house_money_chart(house):
    rows_def = ["Toss-up", "Lean", "Likely"]
    pts = [r for r in house if r["challenger_or_open"] == "1" and r["rating_bucket"] in rows_def
           and r["faction"] in ROWS and r["estab_per_voter"] not in ("", None)]
    lo, hi = 0, 80
    row_h, top = 74, 14
    h = top + row_h * len(rows_def) + 48
    hl = 200
    sx = scale(lo, hi, hl, W - MR)
    body = [x_axis(sx, lo, hi, 10, top, top + row_h * len(rows_def), fmt=lambda t: f"${t:.0f}",
                   label="Party committee and party super PAC money per vote cast (US dollars)")]
    names = {"CA-22": ("Villegas", 7, -6, "start"), "MI-07": ("Lawrence", 7, 16, "start"), "ME-02": ("Dunlap", 0, -10, "middle"),
             "VA-05": ("Perriello", -8, 16, "start"), "TN-09": ("Pearson", 7, -8, "start")}
    table_rows = []
    for i, rb in enumerate(rows_def):
        cy = top + row_h * i + row_h / 2
        rr = [r for r in pts if r["rating_bucket"] == rb]
        mods = [float(r["estab_per_voter"]) for r in rr if r["faction"] == "moderate"]
        body.append(f'<text x="{hl - 14}" y="{cy - 4:.1f}" class="row-label" text-anchor="end">{esc(rb)}</text>')
        body.append(f'<text x="{hl - 14}" y="{cy + 12:.1f}" class="row-sub" text-anchor="end">n={len(rr)}, moderate median ${st.median(mods):.0f}</text>')
        body.append(f'<line x1="{sx(st.median(mods)):.1f}" x2="{sx(st.median(mods)):.1f}" y1="{cy - row_h * 0.4:.1f}" '
                    f'y2="{cy + row_h * 0.4:.1f}" class="median" style="stroke:var(--moderate)"/>')
        for r in sorted(rr, key=lambda r: r["faction"] == "progressive"):
            v = float(r["estab_per_voter"])
            label, color, shape = FACTION[r["faction"]]
            yy = cy + jitter(r["code"], row_h * 0.28)
            rtb = f", Red to Blue {r['red_to_blue_date']}" if r["red_to_blue"] == "1" else ""
            body.append(mark(shape, sx(min(v, hi)), yy, color,
                             f"{r['code']}: {r['dem_nominee']} ({label.lower()}), ${v:.2f} per vote{rtb}; "
                             f"{'won' if r['dem_won'] == '1' else 'lost'}", 4))
            if r["code"] in names:
                nm, dx, dy, anc = names[r["code"]]
                body.append(f'<text x="{sx(min(v, hi)) + dx:.1f}" y="{yy + dy:.1f}" class="point-label" text-anchor="{anc}">{nm}</text>')
            table_rows.append((rb, r["code"], r["dem_nominee"], label, f"${v:.2f}", "yes" if r["red_to_blue"] == "1" else "no",
                               "won" if r["dem_won"] == "1" else "lost"))
    return svg(h, "".join(body), "Party money for House challengers by race rating",
               "Strip plot of Democratic challengers and open-seat nominees in Toss-up, Lean and Likely seats: x is party "
               "committee and House Majority PAC money per vote cast, rows are race ratings, with the moderate median marked."), table_rows


# ---------------------------------------------------------------- page

LINK_ICON = ('<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path fill="none" stroke="currentColor" '
             'stroke-width="1.6" stroke-linecap="round" d="M6.5 9.5l3-3M7 4.5l1.2-1.2a2.8 2.8 0 014 4L11 8.5M9 11.5l-1.2 1.2a2.8 2.8 0 01-4-4L5 7.5"/></svg>')


def slug(text):
    t = re.sub(r"<[^>]+>", "", text).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60]


def heading_anchors(page):
    """Give every h2/h3 in the article an id and a small copy-link button."""
    seen = set(re.findall(r'id="([^"]+)"', page))

    def fix(m):
        level, attrs, inner = m.group(1), m.group(2) or "", m.group(3)
        found = re.search(r'id="([^"]+)"', attrs)
        if found:
            hid = found.group(1)
        else:
            hid = base = slug(inner)
            n = 2
            while hid in seen:
                hid = f"{base}-{n}"
                n += 1
            seen.add(hid)
            attrs = f' id="{hid}"' + attrs
        btn = (f'<button class="anchor" type="button" data-anchor="{hid}" '
               f'aria-label="Copy link to this section" title="Copy link to this section">{LINK_ICON}</button>')
        return f"<h{level}{attrs}>{inner}{btn}</h{level}>"

    head, body = page.split("<main>", 1)
    body = re.sub(r"<h([23])((?:\s[^>]*)?)>(.*?)</h\1>", fix, body, flags=re.S)
    return head + "<main>" + body

def table(head, rows):
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def figure(fid, chart, caption, legend_keys=None, data_table=None, extra_legend=""):
    lg = legend(legend_keys) if legend_keys else ""
    if extra_legend:
        lg = lg[:-len("</div>")] + extra_legend + "</div>" if lg else f'<div class="legend">{extra_legend}</div>'
    dt = f'<details><summary>Show the numbers as a table</summary>{data_table}</details>' if data_table else ""
    return f'<figure id="{fid}">{lg}<div class="chart">{chart}</div><figcaption>{caption}</figcaption>{dt}</figure>'


def main():
    house, state = load()
    SITE.mkdir(exist_ok=True)
    (SITE / "data").mkdir(exist_ok=True)
    for f in ("house_2026.csv", "statewide_2026.csv", "senate_money_2026.csv", "house_money_2026.csv"):
        shutil.copy(HERE / "data" / f, SITE / "data" / f)

    def grp(f, field):
        v = [r[field] for r in house if r["faction"] == f and r[field] is not None]
        return len(v), st.mean(v), st.median(v)

    tide = strip_chart(house, "overperf", -10, 50, 10, "How far the Democrat ran ahead of Harris's 2024 margin (points)",
                       "House overperformance by faction",
                       "Strip plot of 410 House races: each dot is one Democratic nominee, rows are factions, "
                       "x is how far the nominee ran ahead of the 2024 presidential margin; a tick marks each median.",
                       tipfmt=house_tip)
    where = strip_chart(house, "pres24_margin", -50, 90, 10, "2024 presidential margin in the district (Harris minus Trump)",
                        "Where each faction's nominees ran",
                        "Strip plot of 410 House races by 2024 presidential margin of the district, rows are factions; "
                        "the shaded band marks competitive seats within 15 points.",
                        band=(-15, 15, "Competitive (within 15)"), tipfmt=house_tip)
    flips_svg, flips = flips_chart(house)
    scatter_svg, slope = scatter_state(state)
    db_svg, pairs = dumbbell(state)

    diffs = [p["dem_margin"] - m["dem_margin"] for p, m, _ in pairs]
    mean_d = st.mean(diffs)
    se_d = st.stdev(diffs) / math.sqrt(len(diffs))
    t6 = 2.447
    forest_rows = [
        ("Before 2026", [
            ("Split Ticket, Blue Dogs vs progressives, 2018–2024", 5.0, None, False, "Split Ticket WAR, about 5 points"),
            ("G. Elliott Morris, 2024 model", 1.25, (1.0, 1.5), False, "Morris: about 1 to 1.5 points in 2024"),
            ("Bonica and Grumbach, 2024 model", 0.0, None, False, "Bonica and Grumbach: about zero"),
        ]),
        ("2026 House", [
            ("Split Ticket, Blue Dogs vs progressive caucus", 3.0, None, False, "The Argument: 'a little over 3 points'"),
            ("This page, broad factions, all 410 seats", 0.23, (-2.20, 2.66), True, "+0.2 (95% CI −2.2 to +2.7), p=0.85"),
            ("This page, broad factions, 132 competitive seats", -1.88, (-6.94, 3.19), True, "−1.9 (95% CI −6.9 to +3.2), p=0.47"),
            ("This page, strict factions, all seats", 3.11, (-1.80, 8.02), True, "+3.1 (95% CI −1.8 to +8.0), p=0.21"),
            ("This page, strict, without 7 Hispanic-district outliers", 2.25, (-1.65, 6.15), True, "+2.3 (95% CI −1.7 to +6.2), p=0.26"),
        ]),
        ("2026 Senate and governor", [
            ("This page, 7 same-ballot pairs", -mean_d, (-mean_d - t6 * se_d, -mean_d + t6 * se_d), True,
             f"{signed(-mean_d)} (95% CI {signed(-mean_d - t6 * se_d)} to {signed(-mean_d + t6 * se_d)})"),
            ("This page, MI, MN, ME pairs, vote share", 1.73, (1.3, 2.1), True, "Vote-share gaps 2.1, 1.8, 1.3"),
            ("This page, regression with controls, 65 races", 5.93, (0.83, 11.03), True, "+5.9 (95% CI +0.8 to +11.0)"),
            ("CWCP, Sanders Senate endorsees on WAR", 8.0, None, False, "About 8 points behind other Senate nominees"),
        ]),
    ]
    forest_svg = forest(forest_rows)
    forest_table = table(["Estimate", "Moderate advantage", "Range or 95% interval", "Source"],
                         [(lab, signed(est), f"{signed(ci[0])} to {signed(ci[1])}" if ci else "not published",
                           "this page" if own else "published") for g, items in forest_rows for lab, est, ci, own, _ in items])

    n_close = sum(1 for r in flips if r["dem_margin"] < 3)
    n_close5 = sum(1 for r in flips if r["dem_margin"] < 5)
    flip_counts = {f: sum(1 for r in flips if r["faction"] == f) for f in ROWS}
    lost_close = [r for r in house if r["winner_party"] == "R" and r["dem_margin"] is not None and -3 < r["dem_margin"] < 0]

    def where_stats(f):
        v = [r["pres24_margin"] for r in house if r["faction"] == f]
        return len(v), st.median(v), sum(1 for x in v if abs(x) <= 15), sum(1 for x in v if x < 0)

    ws = {f: where_stats(f) for f in ROWS}
    g = {f: grp(f, "overperf") for f in ROWS}

    tide_table = table(["Faction", "Nominees", "Mean overperformance", "Median"],
                       [(FACTION[f][0], g[f][0], signed(g[f][1]), signed(g[f][2])) for f in ROWS])
    where_table = table(["Faction", "Nominees", "Median 2024 seat", "In competitive seats", "In Trump-won seats"],
                        [(FACTION[f][0], ws[f][0], signed(ws[f][1]), ws[f][2], ws[f][3]) for f in ROWS])
    flips_table = table(["Seat", "Democrat", "Margin", "Faction"],
                        [(r["code"], r["dem_nominee"], signed(r["dem_margin"]), FACTION[r["faction"]][0]) for r in flips])
    pair_table = table(["State", "Progressive", "Margin", "Moderate", "Margin", "Difference"],
                       [(p["state"], f'{p["dem_nominee"]} ({p["office"]})', signed(p["dem_margin"]),
                         f'{m["dem_nominee"]} ({m["office"]})', signed(m["dem_margin"]), signed(d)) for p, m, d in pairs])
    state_table = table(["State", "Office", "Democrat", "Faction", "2024 margin", "2026 margin", "Swing"],
                        [(r["st"], r["office"], r["dem_nominee"], FACTION[r["faction"]][0], signed(r["pres2024_margin"]),
                          signed(r["dem_margin"]), signed(r["swing_vs_2024"]))
                         for r in sorted(state, key=lambda r: -r["swing_vs_2024"])])

    sen_money, house_money = load_money()
    sen_money_svg, sen_rows = senate_money_chart(sen_money)
    house_money_svg, hm_rows = house_money_chart(house_money)
    sen_money_table = table(["Race", "Rating", "Faction", "Party money for Democrat, per adult", "All outside money against, per adult", "Share matched"],
                            [(f'{r["st"]} {r["democrat"]}', r["cook_final"], FACTION[MONEY_FACTION[r["faction"]]][0],
                              f"${party:.2f}", f"${against:.2f}", share) for r, party, against, share in sen_rows])
    house_money_table = table(["Rating", "Seat", "Democrat", "Faction", "Party money per vote", "Red to Blue", "Result"], hm_rows)

    page = TEMPLATE
    subs = {
        "FIG_TIDE": figure("fig-tide", tide,
                           "Each dot is one of 410 Democratic House nominees in a two-party race. The tick in each row is the median. "
                           "Hover or tap a dot for the race. The far-right dots are heavily Hispanic seats in South Texas and the Central Valley.",
                           ROWS, tide_table),
        "FIG_WHERE": figure("fig-where", where,
                            "The same 410 nominees, placed by how their district voted in 2024. The shaded band is the competitive range.",
                            ROWS, where_table),
        "FIG_FLIPS": figure("fig-flips", flips_svg,
                            "One dot per flipped seat, stacked in one-point bins. The shaded strip holds the seats a 3-point handicap would have reversed.",
                            ROWS, flips_table),
        "FIG_SCATTER": figure("fig-scatter", scatter_svg,
                              "65 Senate and governor races with a Democrat against a Republican. The dashed line is the average relationship across all of them: each point of 2024 Trump margin goes with about 0.27 more points of Democratic swing. Vermont's governor race, where the Democrat swung −38 points against a popular Republican incumbent, is drawn at the bottom edge.",
                              ["moderate", "progressive", "mixed-unclear"], state_table),
        "FIG_PAIRS": figure("fig-pairs", db_svg,
                            "States where one statewide Democrat was progressive and the other moderate. Margins are Democratic minus Republican share.",
                            ["moderate", "progressive"], pair_table),
        "FIG_FOREST": figure("fig-forest", forest_svg,
                             "Filled dots are this page's estimates, hollow dots are published ones. Lines show a 95% interval or a published range; "
                             "a dot without a line had no interval published. Positive numbers favour moderates.",
                             None, forest_table),
        "FIG_SEN_MONEY": figure("fig-senate-money", sen_money_svg,
                                "Contested Senate races, grouped by the Cook Political Report's final rating. The coloured mark is spending for the Democrat by the "
                                "Senate Majority PAC network and the DSCC's independent spending. The grey tick is all outside spending against the Democrat. "
                                "Both are general-election independent expenditures per adult resident (2024 voting-age population). "
                                "Party coordinated spending is not included. The right column is the first as a share of the second.",
                                ["moderate", "progressive", "mixed-unclear"], sen_money_table,
                                extra_legend='<span class="lg"><svg width="14" height="16" viewBox="0 0 14 16" aria-hidden="true">'
                                             '<line x1="7" x2="7" y1="0" y2="16" class="against"/></svg>Spent against the Democrat</span>'),
        "FIG_HOUSE_MONEY": figure("fig-house-money", house_money_svg,
                                  "Democratic challengers and open-seat nominees in seats rated Toss-up, Lean or Likely. Money is DCCC coordinated "
                                  "spending through October 13 plus House Majority PAC independent spending through Election Day, per vote cast. "
                                  "The blue tick is the moderate median in each row.",
                                  ROWS, house_money_table),
        "N_CLOSE": str(n_close), "N_CLOSE5": str(n_close5), "N_FLIPS": str(len(flips)),
        "FLIP_MOD": str(flip_counts["moderate"]), "FLIP_BOTH": str(flip_counts["both"]),
        "FLIP_PROG": str(flip_counts["progressive"]), "FLIP_NONE": str(flip_counts["unflagged"]),
        "LOST_CLOSE": str(len(lost_close)),
        "MOD_MEAN": signed(g["moderate"][1]), "PROG_MEAN": signed(g["progressive"][1]),
        "BOTH_MEAN": signed(g["both"][1]), "NONE_MEAN": signed(g["unflagged"][1]),
        "PROG_N": str(ws["progressive"][0]), "MOD_N": str(ws["moderate"][0]),
        "PROG_MED": signed(ws["progressive"][1]), "MOD_MED": signed(ws["moderate"][1]),
        "PROG_COMP": str(ws["progressive"][2]), "MOD_COMP": str(ws["moderate"][2]),
        "PROG_TRUMP": str(ws["progressive"][3]), "MOD_TRUMP": str(ws["moderate"][3]),
        "SLOPE": f"{abs(slope):.2f}", "PAIR_MEAN": signed(mean_d),
    }
    for k, v in subs.items():
        page = page.replace("{{" + k + "}}", v)
    assert "{{" not in page, page[page.index("{{"):page.index("{{") + 40]
    page = heading_anchors(page)
    (SITE / "index.html").write_text(page, encoding="utf-8")
    (SITE / ".nojekyll").write_text("")
    print("wrote", SITE / "index.html")


TEMPLATE = (HERE / "page.html").read_text(encoding="utf-8")

if __name__ == "__main__":
    main()
