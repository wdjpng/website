// Shared helpers for the three concept prototypes.
// Catalog + posters are local copies; video streams straight from the live archive.
export const MEDIA = ''; // same origin: serve.py proxies /media/* (the live site forbids cross-origin embedding)

export async function loadCatalog() {
  const d = await (await fetch('./catalog.json')).json();
  // tapes.json: what is actually on each unlabeled VHS tape (identified from the recordings)
  const tapes = await fetch('./tapes.json').then(r => r.ok ? r.json() : {}).catch(() => ({}));
  return d.videos.map(v => {
    const t = tapes[v.id], known = t && t.title && t.title !== '?';
    return {
      ...v,
      play: known ? t.title : null,
      note: t?.note || null,
      poster: '.' + v.poster.replace('/assets', ''),
      src: MEDIA + v.versions[0].src,
      short: known ? t.title : shortTitle(v),
    };
  });
}

function shortTitle(v) {
  if (v.category === 'vhs') return 'Band ' + v.title.split('·').pop().trim();
  return v.title;
}

export const fmt = s => {
  s = Math.max(0, Math.floor(s || 0));
  const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, x = s % 60;
  return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0');
};

export const minutes = s => Math.round(s / 60) + ' Min.';

// Remember position per recording (a "bookmark" in the tape, so to speak).
export const pos = {
  get: id => +localStorage.getItem('fid-pos-' + id) || 0,
  set: (id, t) => localStorage.setItem('fid-pos-' + id, Math.floor(t)),
};
