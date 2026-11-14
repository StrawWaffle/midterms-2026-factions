// Page interactions. The charts are complete without any of this (most readers never interact);
// it adds details on demand and links the charts together:
//  - hover or tap a mark for its details (tooltip)
//  - click or tap a race, or find it in the search box, to select it: the same race is marked
//    in every chart and its facts stay in a bar at the bottom while you scroll (linked highlighting)
//  - press a legend entry to highlight one faction in every chart; others fade, axes stay put
//  - Escape clears both
import { select, selectAll } from 'd3';

interface Entity { key: string; label: string; facts: string }

const entities: Entity[] = JSON.parse(document.getElementById('entities')?.textContent || '[]');
const byKey = new Map(entities.map((e) => [e.key, e]));
const byLabel = new Map(entities.map((e) => [e.label.toLowerCase(), e]));
const body = select(document.body);

// ------------------------------------------------------------------ tooltip
const tip = select<HTMLDivElement, unknown>('#tip');
function showTip(el: Element, x: number, y: number) {
  const node = tip.node()!;
  tip.text(el.getAttribute('data-tip') || '').style('display', 'block');
  const w = node.offsetWidth, h = node.offsetHeight;
  tip.style('left', `${Math.max(8, Math.min(x + 14, innerWidth - w - 8))}px`)
    .style('top', `${Math.max(8, y + 14 + h > innerHeight ? y - h - 10 : y + 14)}px`);
}
const hideTip = () => tip.style('display', 'none');
document.addEventListener('pointermove', (e) => {
  if (e.pointerType !== 'mouse') return;
  const el = (e.target as Element).closest?.('[data-tip]');
  if (el && el.getAttribute('data-tip')) showTip(el, e.clientX, e.clientY);
  else hideTip();
});
document.addEventListener('scroll', hideTip, { passive: true });

// ------------------------------------------------------------------ linked selection
let selected: string | null = null;
const bar = select('#selbar');

function clearSelection() {
  selected = null;
  selectAll('.mk.sel').classed('sel', false);
  selectAll('.sel-label').remove();
  body.classed('has-sel', false).classed('has-selbar', false);
  bar.classed('on', false);
}

function selectKey(key: string, scroll = false) {
  clearSelection();
  const marks = selectAll<SVGElement, unknown>(`.mk[data-key="${CSS.escape(key)}"]`);
  if (marks.empty()) return;
  selected = key;
  marks.classed('sel', true).raise();
  // name the selected mark directly in each chart it appears in (skip the invisible hit targets)
  const charts = new Set<SVGSVGElement>();
  marks.each(function () {
    const svgEl = this.ownerSVGElement;
    if (!svgEl || charts.has(svgEl) || this.getAttribute('fill') === 'transparent') return;
    charts.add(svgEl);
    const b = (this as SVGGraphicsElement).getBBox();
    const vbW = svgEl.viewBox.baseVal.width;
    const right = b.x + b.width + 6 + 60 < vbW;
    select(svgEl).append('text').attr('class', 'sel-label')
      .attr('x', right ? b.x + b.width + 6 : b.x - 6).attr('y', b.y - 3)
      .attr('text-anchor', right ? 'start' : 'end').text(key.replace('-Senate', ' Sen').replace('-Governor', ' Gov'));
  });
  body.classed('has-sel', true).classed('has-selbar', true);
  const e = byKey.get(key);
  bar.select('strong').text(e ? e.label : key);
  bar.select('.facts').text(e ? e.facts : '');
  bar.select('.where').text(`Marked in ${charts.size} chart${charts.size === 1 ? '' : 's'}`);
  bar.classed('on', true);
  if (scroll) (marks.node() as Element).closest('figure')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

document.addEventListener('click', (e) => {
  const el = (e.target as Element).closest?.('.mk[data-key]');
  if (el) {
    const key = el.getAttribute('data-key')!;
    if (key === selected) clearSelection();
    else selectKey(key);
    // touch has no hover: show the tooltip on tap
    if ((e as PointerEvent).pointerType !== 'mouse') {
      const r = el.getBoundingClientRect();
      showTip(el, r.right, r.bottom);
    }
    return;
  }
  if (!(e.target as Element).closest?.('#selbar, .find, .lg')) hideTip();
});
bar.select('button').on('click', clearSelection);

// search box: pick a race from the list
const input = document.getElementById('find-input') as HTMLInputElement | null;
if (input) {
  const pick = () => {
    const q = input.value.trim().toLowerCase();
    if (!q) return;
    const exact = byLabel.get(q) || entities.find((en) => en.key.toLowerCase() === q);
    const hit = exact || entities.find((en) => en.label.toLowerCase().includes(q));
    if (hit) { selectKey(hit.key, true); input.value = hit.label; }
  };
  input.addEventListener('change', pick);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); pick(); } });
}

// ------------------------------------------------------------------ faction highlight
function setHighlight(f: string | null) {
  if (f) document.body.dataset.hl = f;
  else delete document.body.dataset.hl;
  selectAll<HTMLButtonElement, unknown>('[data-hl-toggle]').attr('aria-pressed', function () {
    return String(this.dataset.hlToggle === f);
  });
}
document.addEventListener('click', (e) => {
  const b = (e.target as Element).closest?.('[data-hl-toggle]') as HTMLButtonElement | null;
  if (!b) return;
  const f = b.dataset.hlToggle!;
  setHighlight(document.body.dataset.hl === f ? null : f);
});

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  clearSelection();
  setHighlight(null);
  hideTip();
});

// ------------------------------------------------------------------ copy a link to a section
document.addEventListener('click', (e) => {
  const b = (e.target as Element).closest?.('.anchor') as HTMLButtonElement | null;
  if (!b) return;
  const id = b.dataset.anchor!;
  const url = location.href.split('#')[0] + '#' + id;
  const done = () => { b.classList.add('copied'); setTimeout(() => b.classList.remove('copied'), 1400); };
  try { history.replaceState(null, '', '#' + id); } catch { /* ignore */ }
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(done, () => prompt('Copy this link:', url));
  else prompt('Copy this link:', url);
});

// ------------------------------------------------------------------ contents sidebar: mark the section being read
const tocLinks = Array.from(document.querySelectorAll<HTMLAnchorElement>('.toc li a'));
const tocTargets = tocLinks.map((a) => document.getElementById(a.getAttribute('href')!.slice(1)));
let tocActive: HTMLAnchorElement | null = null;
let ticking = false;
function tocUpdate() {
  ticking = false;
  let current = -1;
  tocTargets.forEach((t, i) => { if (t && t.getBoundingClientRect().top <= 120) current = i; });
  const link = current >= 0 ? tocLinks[current] : null;
  if (link === tocActive) return;
  tocActive?.classList.remove('active');
  tocActive = link;
  if (!link) return;
  link.classList.add('active');
  const box = link.closest('.toc-inner') as HTMLElement | null;
  if (box && box.offsetParent !== null) {
    const r = link.getBoundingClientRect(), bb = box.getBoundingClientRect();
    if (r.top < bb.top + 40 || r.bottom > bb.bottom - 40) box.scrollTop += r.top - bb.top - bb.height / 3;
  }
}
if (tocLinks.length) {
  addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(tocUpdate); } }, { passive: true });
  tocUpdate();
}

// ------------------------------------------------------------------ theme toggle
const themeBtn = document.getElementById('theme') as HTMLButtonElement | null;
const current = () => document.documentElement.getAttribute('data-theme')
  || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
const label = () => { if (themeBtn) themeBtn.textContent = current() === 'dark' ? 'Light mode' : 'Dark mode'; };
label();
themeBtn?.addEventListener('click', () => {
  const next = current() === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('theme', next); } catch { /* ignore */ }
  label();
});
