// Notice when a newer build is published (the same scheme as the other StrawWaffle sites).
// On load: if the page came from a stale cache, reload once with a cache-busting address.
// While open: check every 10 minutes and when the tab comes back into view, and offer a
// reload with a short note on what changed.
const body = document.body;
const BASE = body.dataset.base || '/';
const mine = { data: body.dataset.vdata, code: body.dataset.vcode, called: +(body.dataset.vcalled || 0) };

interface Version { data: string; code: string; called: number; seats: number }

async function latest(): Promise<Version | null> {
  try {
    const r = await fetch(`${BASE}version.json?t=${Date.now()}`, { cache: 'no-store' });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

function describe(v: Version) {
  const data = v.data !== mine.data, code = v.code !== mine.code;
  const more = v.called - mine.called;
  const what = more > 0 ? `${more} more House race${more === 1 ? '' : 's'} called` : 'updated results or spending figures';
  if (data && code) return `The page has been updated, with new data: ${what}.`;
  if (data) return `New data is out: ${what}.`;
  return 'The page has been updated.';
}

function banner(v: Version) {
  if (document.getElementById('newver')) return;
  const el = document.createElement('div');
  el.id = 'newver';
  el.className = 'newver';
  el.setAttribute('role', 'status');
  const text = document.createElement('span');
  text.textContent = describe(v);
  el.append(text);
  for (const [a, label] of [['reload', 'Reload'], ['later', 'Later']]) {
    const b = document.createElement('button');
    b.type = 'button';
    b.dataset.a = a;
    b.textContent = label;
    el.append(b);
  }
  el.onclick = (ev) => {
    const a = (ev.target as HTMLElement).dataset.a;
    if (a === 'reload') reloadFresh(v);
    if (a === 'later') el.remove();
  };
  document.body.appendChild(el);
}

// both fingerprints, so a data-only update also changes the address
const idOf = (v: Version) => v.code.slice(0, 6) + v.data.slice(0, 6);

function reloadFresh(v: Version) {
  // a new query string makes GitHub's cache fetch the page again; the #section stays
  const u = new URL(location.href);
  u.searchParams.set('v', idOf(v));
  location.replace(u.toString());
}

const changed = (v: Version | null): v is Version => !!v && (v.data !== mine.data || v.code !== mine.code);

async function check(onLoad: boolean) {
  const v = await latest();
  if (!changed(v)) return;
  // one silent reload per version; after that, ask
  const key = `mf-reloaded-${v.code}-${v.data}`;
  let tried = false;
  try { tried = !!sessionStorage.getItem(key); sessionStorage.setItem(key, '1'); } catch { tried = true; }
  if (onLoad && !tried) reloadFresh(v);
  else banner(v);
}

check(true);
setInterval(() => { if (document.visibilityState === 'visible') check(false); }, 10 * 60 * 1000);
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') check(false); });
