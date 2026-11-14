"""Polite HTTP client: fixed User-Agent, a minimum gap between requests to the same host,
retries with exponential backoff (honouring Retry-After), and conditional GETs for big files."""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "midterms-2026-factions-updater/1.0 (daily data refresh for a static site)"
MIN_GAP = 2.0          # seconds between two requests to the same host
RETRIES = 4            # attempts after the first one
BACKOFF = 5.0          # first retry wait; doubles each time
_last = {}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def _wait(host):
    gap = time.monotonic() - _last.get(host, -1e9)
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    _last[host] = time.monotonic()


def _open(url, headers=None, timeout=120):
    """Open url with retries. Returns the response object, or None on HTTP 304."""
    host = urllib.parse.urlsplit(url).netloc
    wait = BACKOFF
    for attempt in range(RETRIES + 1):
        _wait(host)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return None
            if e.code not in (408, 425, 429, 500, 502, 503, 504) or attempt == RETRIES:
                raise
            ra = e.headers.get("Retry-After", "")
            delay = float(ra) if ra.isdigit() else wait
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == RETRIES:
                raise
            delay = wait
            log(f"  retry {url}: {e}")
        time.sleep(min(delay, 300))
        wait *= 2
    raise RuntimeError("unreachable")


def get_bytes(url, timeout=120):
    with _open(url, timeout=timeout) as r:
        return r.read()


def get_json(url, timeout=120):
    return json.loads(get_bytes(url, timeout).decode("utf-8"))


def download(url, dest: Path, timeout=300):
    """Download url to dest, sending If-None-Match / If-Modified-Since from the last download.
    Returns True if the file changed."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    meta_path = dest.with_name(dest.name + ".meta.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() and dest.exists() else {}
    headers = {}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]
    r = _open(url, headers, timeout)
    if r is None:
        return False
    tmp = dest.with_name(dest.name + ".part")
    with r, open(tmp, "wb") as fh:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
        new_meta = {"url": url, "etag": r.headers.get("ETag", ""), "last_modified": r.headers.get("Last-Modified", "")}
    os.replace(tmp, dest)
    meta_path.write_text(json.dumps(new_meta))
    return True
