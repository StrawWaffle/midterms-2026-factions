"""Read FEC bulk files straight from the downloaded zip (or the plain CSV)."""
import csv
import io
import zipfile

from sources import FEC_FILES


def lines(paths, key, encoding="latin-1"):
    """Yield the lines of a pipe-delimited FEC bulk file."""
    _name, member = FEC_FILES[key]
    with zipfile.ZipFile(paths[key]) as zf:
        with zf.open(member) as raw:
            yield from io.TextIOWrapper(raw, encoding=encoding)


def ie_rows(paths, encoding, errors="strict"):
    """Rows of independent_expenditure_2026.csv as dicts."""
    with open(paths["ie26"], encoding=encoding, errors=errors) as fh:
        yield from csv.DictReader(fh)
