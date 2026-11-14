"""Shared helpers: paths, CSV reading/writing, and pandas-compatible value formatting."""
import csv
import io
import math
from pathlib import Path

csv.field_size_limit(1 << 24)

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
REPO = HERE.parent
DATA = REPO / "public" / "data"


def read_csv(path, encoding="utf-8"):
    with open(path, encoding=encoding, newline="") as fh:
        return list(csv.DictReader(fh))


def is_nan(v):
    return v is None or v == "" or (isinstance(v, float) and math.isnan(v))


def to_float(v):
    """pandas-style numeric parse: '' or unparseable -> None."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fmt_plain(v):
    """How Python's csv module writes a value (the stdlib research scripts)."""
    if v is None:
        return ""
    return str(v)


# Strings pandas.read_csv turns into NaN by default (written back out as empty cells).
PANDAS_NA = {"", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND", "1.#QNAN", "<NA>", "N/A",
             "NA", "NULL", "NaN", "None", "n/a", "nan", "null"}


def fmt_pandas(v, kind):
    """How pandas wrote a value after read_csv -> to_csv, given the column's dtype
    ('float', 'int', 'bool' or 'str')."""
    if is_nan(v) or (isinstance(v, str) and v in PANDAS_NA):
        return ""
    if kind == "float":
        return repr(float(v))
    if kind == "int":
        return str(int(float(v)))
    if kind == "bool":
        if isinstance(v, str):
            return v
        return "True" if v else "False"
    return str(v)


def to_csv_text(rows, columns):
    """Serialise rows (dicts of already-formatted strings) with LF line endings."""
    for r in rows:
        extra = set(r) - set(columns)
        if extra:
            raise ValueError(f"unexpected columns {sorted(extra)}")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in columns})
    return buf.getvalue()


def row_key(r):
    """Row key used in static/overrides.csv: the seat code for House files, '<st> <office>' otherwise."""
    return r["code"] if "code" in r else f"{r['st']} {r['office']}"


def apply_overrides(rows, filename, columns):
    """Apply manual corrections from static/overrides.csv to the formatted rows of one output file."""
    by_key = {row_key(r): r for r in rows}
    for o in read_csv(STATIC / "overrides.csv"):
        if o["file"] != filename or o["value"] == ACCEPT_DROP:
            continue
        if o["column"] not in columns:
            raise ValueError(f"override for unknown column {filename}:{o['column']}")
        if o["key"] not in by_key:
            raise ValueError(f"override for unknown row {filename}:{o['key']}")
        by_key[o["key"]][o["column"]] = o["value"]
    return rows


# ---------------------------------------------------------------- cumulative-money guard
WARNINGS = []
ACCEPT_DROP = "ACCEPT_DROP"  # overrides.csv value: let a genuine drop in this cell through the guard


class Guard:
    """Cumulative FEC figures (receipts, disbursements, IE and coordinated totals) only grow within a cycle.
    A new value more than 10% below the published one is treated as an upstream glitch: the published
    value is kept (and used for everything derived from it) and a warning is recorded."""
    DROP = 0.10

    def __init__(self, filename, prev_rows):
        self.filename = filename
        self.prev = {row_key(r): r for r in prev_rows}
        self.kept = set()
        self.accepted = {(o["key"], o["column"]) for o in read_csv(STATIC / "overrides.csv")
                         if o["file"] == filename and o["value"] == ACCEPT_DROP}

    def keep_with(self, key, col, companions):
        """If `col` was held back for this row, also keep the published companion columns from the same
        FEC report (cash on hand, coverage date), so the row stays one consistent snapshot."""
        if (key, col) not in self.kept:
            return {}
        return {c: self.prev[key][c] for c in companions}

    def check(self, key, col, new, who=""):
        old = to_float(self.prev.get(key, {}).get(col))
        val = to_float(new) if not isinstance(new, (int, float)) else float(new)
        if (key, col) in self.accepted or old is None or old <= 0 or (val is not None and val >= old * (1 - self.DROP)):
            return new
        old_s = self.prev[key][col]
        self.kept.add((key, col))
        WARNINGS.append(f"{self.filename} {key} {col}{f' ({who})' if who else ''}: new value "
                        f"{'missing' if val is None else f'{val:,.2f}'} is more than 10% below the published "
                        f"{old:,.2f}; kept the published value")
        return int(old_s) if old_s.lstrip("-").isdigit() else old
