"""Everything the pipeline downloads, cached under pipeline/cache/ (gitignored).

With fetch=False nothing is downloaded and the cache is read as-is (for testing and re-runs).
A source that fails is recorded in Sources.failures; callers then keep the previously published values.
"""
import json
import re
import urllib.parse
from datetime import datetime, timezone

import net
from common import HERE

CACHE = HERE / "cache"
WIKI_API = "https://en.wikipedia.org/w/api.php"
NBC_STATE = "https://www.nbcnews.com/firecracker/api/v2/state-results/2026-elections/{slug}-house-results"
CA_SOS = "https://api.sos.ca.gov/returns/us-rep/district/{n}"
FEC_BULK = "https://www.fec.gov/files/bulk-downloads/2026/{name}"
# FEC bulk files used by the two money datasets: (download name, member inside the zip or None)
FEC_FILES = {
    "weball26": ("weball26.zip", "weball26.txt"),    # candidate summaries
    "cn26": ("cn26.zip", "cn.txt"),                  # candidate master
    "cm26": ("cm26.zip", "cm.txt"),                  # committee master
    "pas226": ("pas226.zip", "itpas2.txt"),          # committee-to-candidate items: 24C coordinated, 24K contributions
    "ie26": ("independent_expenditure_2026.csv", None),
}
NBC_NAMES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california", "CO": "colorado",
    "CT": "connecticut", "DE": "delaware", "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas", "KY": "kentucky", "LA": "louisiana",
    "ME": "maine", "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota",
    "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new-hampshire", "NJ": "new-jersey", "NM": "new-mexico", "NY": "new-york", "NC": "north-carolina",
    "ND": "north-dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon", "PA": "pennsylvania",
    "RI": "rhode-island", "SC": "south-carolina", "SD": "south-dakota", "TN": "tennessee", "TX": "texas",
    "UT": "utah", "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west-virginia",
    "WI": "wisconsin", "WY": "wyoming"}
NBC_DISTRICT = "https://www.nbcnews.com/politics/2026-elections/{slug}-us-house-district-{n}-results"
# Ranked-choice states: the state feed switches to the final RCV round once AP tabulates it. The research
# build used the first-round general-election count from the district page, so these are read from there.
RCV_STATES = {"AK", "ME"}
NBC_PARTY = {"dem": "Dem", "gop": "Rep", "rep": "Rep", "ind": "Ind", "lib": "Lib", "grn": "Grn", "other": "Oth"}


def _nbc_race(v):
    return {"totalVote": v.get("totalVote"), "percentIn": v.get("percentIn"), "isCalled": v.get("isCalled"),
            "candidates": [{"name": c.get("name"),
                            "party": NBC_PARTY.get(str(c.get("party")).lower(), str(c.get("party")).title()),
                            "vote": c.get("votes", c.get("vote")), "isWinner": c.get("isWinner")}
                           for c in v.get("candidates") or []]}


def _safe(title):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", title.replace(" ", "_"))


class Sources:
    def __init__(self, fetch=True, cache=CACHE):
        self.fetch = fetch
        self.cache = cache
        self.failures = []

    def fail(self, what, err):
        self.failures.append(f"{what}: {err}")
        net.log(f"FAILED {what}: {err}")

    # ------------------------------------------------------------------ Wikipedia
    def wikitexts(self, titles, batch=10):
        """Current wikitext of each page title (redirects followed). Missing pages are left out."""
        out = {}
        d = self.cache / "wiki"
        todo = list(titles)
        if self.fetch:
            d.mkdir(parents=True, exist_ok=True)
            for i in range(0, len(todo), batch):
                chunk = todo[i:i + batch]
                try:
                    got = self._wiki_query(chunk)
                except Exception as e:  # noqa: BLE001 - report, fall back to cache
                    self.fail(f"Wikipedia {chunk[0]}..", e)
                    continue
                for t, text in got.items():
                    (d / (_safe(t) + ".txt")).write_text(text, encoding="utf-8")
        for t in todo:
            p = d / (_safe(t) + ".txt")
            if p.exists():
                out[t] = p.read_text(encoding="utf-8")
            elif not self.fetch:
                self.fail(f"Wikipedia {t}", "not in cache")
        return out

    def _wiki_query(self, titles):
        params = {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                  "format": "json", "formatversion": "2", "redirects": "1", "titles": "|".join(titles)}
        found, cont = {}, {}
        alias = {t: t for t in titles}
        while True:
            js = net.get_json(WIKI_API + "?" + urllib.parse.urlencode({**params, **cont}))
            q = js.get("query", {})
            for kind in ("normalized", "redirects"):
                for m in q.get(kind, []):
                    for t, cur in list(alias.items()):
                        if cur == m["from"]:
                            alias[t] = m["to"]
            for p in q.get("pages", []):
                revs = p.get("revisions")
                if revs:
                    found[p["title"]] = revs[0]["slots"]["main"]["content"]
            if "continue" not in js:
                break
            cont = js["continue"]
        out = {}
        for t in titles:
            if alias[t] in found:
                out[t] = found[alias[t]]
            else:
                self.fail(f"Wikipedia {t}", "page missing")
        return out

    # ------------------------------------------------------------------ NBC News (AP results)
    def nbc_states(self, seats):
        """seats: {state: [district numbers]}. Returns {state: {"url", "fetched", "districts": {"01": race}}}
        from NBC's per-state House results feed (district pages for ranked-choice states).
        Each race: totalVote, percentIn, isCalled, candidates [{name, party (Dem/Rep/..), vote, isWinner}]."""
        d = self.cache / "nbc"
        out = {}
        for st, districts in seats.items():
            p = d / f"{st}.json"
            if self.fetch:
                try:
                    if st in RCV_STATES:
                        url = NBC_DISTRICT.format(slug=NBC_NAMES[st], n="{n}")
                        found = {}
                        for n in districts:
                            found.update(self._nbc_district(st, n or 1))
                    else:
                        url = NBC_STATE.format(slug=NBC_NAMES[st])
                        found = {k: v for race in net.get_json(url).get("races") or []
                                 for k, v in (race.get("mapData") or {}).items()}
                    if not found:
                        raise ValueError("no districts in feed")
                    d.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps({"url": url, "fetched": datetime.now(timezone.utc).isoformat(),
                                             "districts": {k: _nbc_race(v) for k, v in found.items()}}), encoding="utf-8")
                except Exception as e:  # noqa: BLE001
                    self.fail(f"NBC {st}", e)
                    continue
            if p.exists():
                out[st] = json.loads(p.read_text(encoding="utf-8"))
            else:
                self.fail(f"NBC {st}", "not in cache")
        return out

    def _nbc_district(self, st, n):
        """mapData of the first-round general-election race on a district page."""
        html = net.get_bytes(NBC_DISTRICT.format(slug=NBC_NAMES[st], n=n)).decode("utf-8", "replace")
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        races = json.loads(m.group(1))["props"]["pageProps"]["races"]
        general = [r for r in races if (r.get("summary") or {}).get("electionTypeCode") == "G"]
        race = (general or races)[-1]
        return {f"{n:02d}": v for v in (race.get("mapData") or {}).values()}

    # ------------------------------------------------------------------ California Secretary of State
    def ca_districts(self, districts):
        d = self.cache / "ca"
        out = {}
        for n in districts:
            p = d / f"{n}.json"
            if self.fetch:
                try:
                    js = net.get_json(CA_SOS.format(n=n))
                    d.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps(js), encoding="utf-8")
                except Exception as e:  # noqa: BLE001
                    self.fail(f"CA SoS {n}", e)
                    continue
            if p.exists():
                out[n] = json.loads(p.read_text(encoding="utf-8"))
        return out

    # ------------------------------------------------------------------ FEC bulk files
    def fec(self):
        """Download (conditionally) the FEC bulk files. Returns {key: path} for the files available."""
        d = self.cache / "fec"
        out = {}
        for key, (name, _member) in FEC_FILES.items():
            p = d / name
            if self.fetch:
                try:
                    changed = net.download(FEC_BULK.format(name=name), p, timeout=600)
                    net.log(f"FEC {name}: {'downloaded' if changed else 'not modified'}")
                except Exception as e:  # noqa: BLE001
                    self.fail(f"FEC {name}", e)
            if p.exists():
                out[key] = p
            else:
                self.fail(f"FEC {name}", "not available")
        return out
