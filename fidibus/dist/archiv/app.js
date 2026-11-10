const $ = (id) => document.getElementById(id);
const categories = { stage: 'Vorstellung', vhs: 'VHS-Schatz', short: 'Kurzfilm', backstage: 'Hinter den Kulissen' };
const titles = { available: 'Schon jetzt zum Anschauen', all: 'Geschichten zum Wiederentdecken', stage: 'Vorhang auf für grosse Geschichten', vhs: 'Kleine Zeitreisen auf Videoband', short: 'Ein Vorgeschmack auf den Zauber', backstage: 'Ein Blick hinter den Vorhang', saved: 'Deine kleine Schatzkammer' };
const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
const write = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} };
let saved = new Set(read('fidibus-saved', []));
let progress = read('fidibus-progress', {});
let videos = [], filter = 'all', current = null, currentVersion = null, lastProgress = 0, toastTimer;
let availability = null, heroId = 'dvd-001-2';
const isReady = (version) => !availability || availability.has(version.id + '.mp4');
const canWatch = (video) => video.versions.some(isReady);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fold = (s) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const time = (s) => { const n = Math.round(s); return n >= 3600 ? `${Math.floor(n / 3600)}:${String(Math.floor(n % 3600 / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}` : `${Math.floor(n / 60)}:${String(n % 60).padStart(2, '0')}`; };
const length = (s) => s >= 3600 ? `${Math.floor(s / 3600)} Std. ${Math.round(s % 3600 / 60)} Min.` : `${Math.max(1, Math.round(s / 60))} Min.`;
const urlFor = (v) => `/archiv/?watch=${encodeURIComponent(v.id)}`;
function toast(message) { $('toast').textContent = message; $('toast').classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').classList.remove('visible'), 3200); }
function saveButton(v) { return `<button class="save-card ${saved.has(v.id) ? 'saved' : ''}" data-save="${v.id}" aria-label="${saved.has(v.id) ? 'Aus Merkliste entfernen' : 'Zur Merkliste hinzufügen'}: ${esc(v.title)}" aria-pressed="${saved.has(v.id)}">${saved.has(v.id) ? '♥' : '♡'}</button>`; }
function card(v, compact = false) {
  const p = progress[v.id];
  const bar = p && p.time > 10 && p.time < p.duration - 30 ? `<span class="progress-track"><span style="width:${Math.min(100, p.time / p.duration * 100)}%"></span></span>` : '';
  const poster = `<div class="card-image"><img src="${esc(v.poster)}" alt="Szene aus ${esc(v.title)}" loading="lazy" decoding="async"><span class="card-badge">${availability ? canWatch(v) ? 'Jetzt abspielbar' : 'Wird hochgeladen' : esc(categories[v.category])}</span><span class="card-hover-play" aria-hidden="true">${availability && !canWatch(v) ? '◷' : '▶'}</span><span class="duration">${time(v.duration)}</span>${bar}</div>`;
  if (compact) return `<a class="related-card" href="${urlFor(v)}" data-watch="${v.id}">${poster}<div><h3>${esc(v.title)}</h3><p>${esc(v.subtitle || v.season || categories[v.category])}</p></div></a>`;
  return `<article class="video-card"><a href="${urlFor(v)}" data-watch="${v.id}" aria-label="${esc(v.title)} abspielen">${poster}</a><div class="card-title-line"><h3><a href="${urlFor(v)}" data-watch="${v.id}">${esc(v.title)}</a></h3>${saveButton(v)}</div><p class="card-meta">${esc(v.subtitle || v.season || categories[v.category])}${v.versions.length > 1 ? `<span class="dot">·</span>${v.versions.length} Fassungen` : ''}</p></article>`;
}
function render() {
  const q = fold($('search').value.trim());
  let shown = videos.filter((v) => (filter === 'all' || filter === 'available' && canWatch(v) || filter === 'saved' && saved.has(v.id) || v.category === filter) && fold([v.title, v.subtitle, v.season, v.description, v.collection].join(' ')).includes(q));
  const sort = $('sort').value;
  if (sort === 'archive' && availability) shown.sort((a, b) => Number(canWatch(b)) - Number(canWatch(a)));
  if (sort === 'title') shown.sort((a, b) => a.title.localeCompare(b.title, 'de'));
  if (sort === 'year') shown.sort((a, b) => (b.year || 0) - (a.year || 0));
  if (sort === 'duration') shown.sort((a, b) => b.duration - a.duration);
  $('video-grid').innerHTML = shown.map((v) => card(v)).join('');
  $('empty-state').hidden = shown.length > 0;
  $('empty-copy').textContent = q ? 'Zu deiner Suche gibt es noch keinen Treffer. Versuche einen anderen Titel oder eine Bandnummer.' : filter === 'available' ? 'Die ersten Aufnahmen werden gerade hochgeladen.' : 'Tippe auf das Herz bei einer Aufnahme, um sie für später aufzubewahren.';
  $('collection-title').textContent = q ? `Auf der Suche nach „${$('search').value.trim()}“` : titles[filter];
  $('collection-eyebrow').textContent = filter === 'saved' ? 'FÜR EIN ANDERES MAL AUFBEWAHRT' : 'VOM BÜHNENZAUBER ZUM FILMSCHATZ';
  $('result-count').textContent = `${shown.length} ${shown.length === 1 ? 'Aufnahme' : 'Aufnahmen'}`;
  $('all-count').textContent = videos.length;
  $('saved-count').textContent = saved.size;
  document.querySelectorAll('[data-nav], [data-filter]').forEach((b) => { const active = (b.dataset.nav || b.dataset.filter) === filter; b.classList.toggle('active', active); b.setAttribute('aria-pressed', String(active)); });
  const resumed = videos.filter((v) => progress[v.id]?.time > 15 && progress[v.id]?.time < progress[v.id]?.duration - 30).sort((a, b) => progress[b.id].updated - progress[a.id].updated).slice(0, 3);
  $('continue-grid').innerHTML = resumed.map((v) => card(v)).join('');
  $('continue-section').hidden = resumed.length === 0 || filter !== 'all' || !!q;
  updateWatchSave();
}
function updateWatchSave() { if (current) { $('watch-save').textContent = saved.has(current.id) ? '♥ Gemerkt' : '♡ Merken'; $('watch-save').setAttribute('aria-pressed', String(saved.has(current.id))); } }
function toggleSaved(id) { if (saved.has(id)) saved.delete(id); else saved.add(id); write('fidibus-saved', [...saved]); render(); }
function saveProgress() {
  const p = $('player');
  if (!current || !currentVersion || !Number.isFinite(p.duration) || p.currentTime < 1) return;
  progress[current.id] = { time: p.currentTime, duration: p.duration, version: currentVersion.id, updated: Date.now() };
  write('fidibus-progress', progress);
}
function changeVersion(version, start = 0, autoplay = false) {
  saveProgress();
  currentVersion = version;
  const p = $('player');
  $('player-message').hidden = true;
  $('version').value = version.id;
  $('version-duration').textContent = length(version.duration);
  p.poster = current.poster;
  if (availability && !isReady(version)) {
    p.removeAttribute('src'); p.load();
    $('player-message').querySelector('p').textContent = 'Diese Aufnahme wird noch hochgeladen. Unter „Jetzt abspielbar“ findest du die fertigen Videos.';
    $('player-retry').textContent = 'Abspielbare Aufnahmen ansehen';
    $('player-message').hidden = false;
    return;
  }
  $('player-retry').textContent = 'Erneut versuchen';
  p.src = version.src;
  p.onloadedmetadata = () => { if (start > 0 && start < p.duration - 5) p.currentTime = start; if (autoplay) p.play().catch(() => {}); };
  p.load();
}
function watch(id, { versionId, at, autoplay = false, push = true } = {}) {
  const video = videos.find((v) => v.id === id);
  if (!video) { toast('Diese Aufnahme ist nicht im Archiv.'); goHome(false); return; }
  saveProgress(); $('player').pause();
  current = video;
  const remembered = progress[id];
  const explicit = versionId && video.versions.find(v => v.id === versionId);
  const version = explicit || video.versions.find(v => v.id === remembered?.version && isReady(v)) || video.versions.find(isReady) || video.versions[0];
  const start = at !== undefined ? at : remembered?.version === version.id && remembered.time < remembered.duration - 30 ? remembered.time : 0;
  if (push) history.pushState({}, '', urlFor(video));
  $('home').hidden = true; $('watch').hidden = false;
  $('watch-title').textContent = video.title;
  $('watch-meta').textContent = [categories[video.category], video.season || video.subtitle].filter(Boolean).join(' · ');
  $('watch-description').textContent = video.description;
  $('version').innerHTML = video.versions.map((v) => `<option value="${v.id}">${esc(v.label)}${availability && !isReady(v) ? ' · wird hochgeladen' : ''}</option>`).join('');
  $('version-control').hidden = video.versions.length < 2;
  const related = videos.filter((v) => v.id !== id && (!availability || canWatch(v))).sort((a, b) => Number(b.collection === video.collection) - Number(a.collection === video.collection) || Number(b.category === video.category) - Number(a.category === video.category)).slice(0, 6);
  $('related-list').innerHTML = related.map((v) => card(v, true)).join('');
  updateWatchSave();
  document.title = `${video.title} · Fidibus`;
  // The prior recording has already been saved; avoid assigning its playback time to the new one.
  currentVersion = null;
  changeVersion(version, start, autoplay);
  window.scrollTo({ top: 0, behavior: 'instant' });
}
function goHome(push = true) {
  saveProgress(); $('player').pause(); $('player').removeAttribute('src'); $('player').load();
  current = null; currentVersion = null;
  if (push) history.pushState({}, '', '/archiv/');
  $('watch').hidden = true; $('home').hidden = false;
  document.title = 'Fidibus · Ein Archiv voller Geschichten';
  render();
}
function route() {
  const u = new URL(location.href);
  if (u.searchParams.has('watch')) watch(u.searchParams.get('watch'), { versionId: u.searchParams.get('v'), at: u.searchParams.has('t') ? Math.max(0, Number(u.searchParams.get('t')) || 0) : undefined, push: false });
  else goHome(false);
}
document.addEventListener('click', (e) => {
  const target = e.target.closest('[data-watch], [data-save], [data-nav], [data-filter]');
  if (!target || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  if (target.dataset.watch) { e.preventDefault(); watch(target.dataset.watch, { autoplay: true }); }
  if (target.dataset.save) toggleSaved(target.dataset.save);
  const nextFilter = target.dataset.nav || target.dataset.filter;
  if (nextFilter) { filter = nextFilter; if (current) goHome(); render(); $('collection').scrollIntoView({ behavior: 'smooth', block: 'start' }); }
});
$('hero-play').onclick = $('hero-image-play').onclick = () => watch(heroId, { autoplay: true });
$('search-form').onsubmit = (e) => { e.preventDefault(); if (current) goHome(); render(); $('collection').scrollIntoView({ behavior: 'smooth' }); };
$('search').oninput = () => { if (current) goHome(); render(); };
$('sort').onchange = render;
$('watch-back').onclick = (e) => { e.preventDefault(); goHome(); $('collection').scrollIntoView({ block: 'start' }); };
$('watch-save').onclick = () => current && toggleSaved(current.id);
$('version').onchange = () => { const next = current.versions.find((v) => v.id === $('version').value); if (next) { changeVersion(next, 0, !$('player').paused); const u = new URL(location.href); u.searchParams.set('v', next.id); u.searchParams.delete('t'); history.replaceState({}, '', u); } };
$('watch-share').onclick = async () => {
  if (!current) return;
  const u = new URL(urlFor(current), location.origin); u.searchParams.set('v', currentVersion.id);
  try { if (navigator.share) await navigator.share({ title: `${current.title} · Fidibus`, url: u.href }); else { await navigator.clipboard.writeText(u.href); toast('Der Link ist kopiert. Viel Freude beim Teilen!'); } } catch (e) { if (e.name !== 'AbortError') toast('Den Link kannst du aus der Adresszeile kopieren.'); }
};
$('player').addEventListener('timeupdate', () => { if (Date.now() - lastProgress > 5000) { saveProgress(); lastProgress = Date.now(); } });
$('player').addEventListener('pause', saveProgress);
$('player').addEventListener('ended', saveProgress);
$('player').addEventListener('error', async () => {
  if (!current || !$('player').getAttribute('src')) return;
  const source = $('player').getAttribute('src');
  let message = 'Diese Aufnahme lässt sich gerade nicht laden. Bitte versuche es gleich noch einmal.';
  try { const r = await fetch(source, { method: 'HEAD' }); if (r.status === 503 || r.status === 404) message = 'Diese Aufnahme ist noch nicht online. Schau später wieder vorbei.'; } catch {}
  if ($('player').getAttribute('src') !== source || !current) return;
  $('player-message').querySelector('p').textContent = message;
  $('player-message').hidden = false;
});
$('player-retry').onclick = () => { if (currentVersion && availability && !isReady(currentVersion)) { filter = 'available'; goHome(); $('collection').scrollIntoView(); return; } if (currentVersion) changeVersion(currentVersion, progress[current.id]?.time || 0, true); };
for (const id of ['about-open', 'banner-about']) $(id).onclick = () => $('about-dialog').showModal();
$('about-close').onclick = () => $('about-dialog').close();
$('about-dialog').onclick = (e) => { if (e.target === $('about-dialog')) { const r = e.target.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) e.target.close(); } };
addEventListener('popstate', route);
addEventListener('pagehide', saveProgress);
document.addEventListener('visibilitychange', () => { if (document.hidden) saveProgress(); });
document.addEventListener('keydown', (e) => {
  if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) || e.target.isContentEditable || e.metaKey || e.ctrlKey || e.altKey || $('about-dialog').open) return;
  if (e.key === '/') { e.preventDefault(); $('search').focus(); return; }
  if (!current || e.target.closest('button, a')) return;
  const p = $('player');
  if (e.key === ' ' || e.key.toLowerCase() === 'k') { e.preventDefault(); p.paused ? p.play().catch(() => {}) : p.pause(); }
  if (e.key === 'ArrowRight' || e.key.toLowerCase() === 'l') { e.preventDefault(); p.currentTime = Math.min(p.duration || 0, p.currentTime + 10); }
  if (e.key === 'ArrowLeft' || e.key.toLowerCase() === 'j') { e.preventDefault(); p.currentTime = Math.max(0, p.currentTime - 10); }
  if (e.key.toLowerCase() === 'm') p.muted = !p.muted;
  if (e.key.toLowerCase() === 'f') { if (document.fullscreenElement) document.exitFullscreen(); else if (p.requestFullscreen) p.requestFullscreen().catch(() => {}); else if (p.webkitEnterFullscreen) p.webkitEnterFullscreen(); }
});
try {
  const response = await fetch('/catalog.json');
  if (!response.ok) throw new Error('catalog');
  videos = (await response.json()).videos;
  saved = new Set([...saved].filter((id) => videos.some((v) => v.id === id)));
  async function refreshAvailability(initial = false) {
    try {
      const r = await fetch('/media/status', { signal: AbortSignal.timeout(8000) });
      const status = r.ok ? await r.json() : null;
      if (!status || !Array.isArray(status.available)) return;
      availability = new Set(status.available);
      const pending = status.ready < status.total;
      $('available-filter').hidden = !pending;
      if (initial && pending) filter = 'available';
      if (!pending && filter === 'available') filter = 'all';
      const notice = $('archive-notice');
      notice.textContent = `✧ ${status.ready} von ${status.total} Videofassungen sind abspielbar. Die übrigen Aufnahmen werden noch hochgeladen.`;
      notice.hidden = !pending;
      heroId = availability.has('dvd-001-2.mp4') ? 'dvd-001-2' : 'dvd-001-1';
      const trailer = heroId === 'dvd-001-1';
      $('hero-play').innerHTML = `<span>▶</span> ${trailer ? 'Trailer ansehen' : 'Vorhang auf'}`;
      $('hero-image-play').setAttribute('aria-label', trailer ? 'Rotkäppchen-Trailer abspielen' : 'Rotkäppchen abspielen');
      document.querySelector('.hero-picture-caption div > span').textContent = trailer ? 'DER TRAILER · JETZT ABSPIELBAR' : 'DIE GANZE VORSTELLUNG';
      document.querySelector('.hero-time').textContent = trailer ? '4 Min.' : '1 Std. 22 Min.';
      render();
    } catch {}
  }
  await refreshAvailability(true);
  render(); route();
  setInterval(() => refreshAvailability(), 60000);
} catch {
  $('video-grid').innerHTML = '<p class="loading">Das Archiv konnte gerade nicht geladen werden. Bitte lade die Seite noch einmal.</p>';
}
