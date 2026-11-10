# fidibus.munzel.com — Wohnzimmer edition

Lives in `fidibus/` of this repo; excluded from the Jekyll build of munzel.com (`_config.yml`).
Prototypes (Papiertheater, Videorekorder, Litfaßsäule) are in `concepts/` (`python3 concepts/serve.py`).

`dist/` = the live Cloudflare Pages bundle (from ~/Documents/Codex/2026-10-31/i-x20/outputs/fidibus/dist) plus:

- `/` — the living room (VCR) page: `index.html`, `wohnzimmer.js`, `wohnzimmer-shared.js`, `tapes.json`,
  self-hosted fonts in `assets/fonts/wohnzimmer/` (the site CSP only allows 'self').
- `/archiv/` — the previous list archive, unchanged except that its links now stay under `/archiv/`.
  Old shared links `/?watch=<id>` are forwarded there (`wohnzimmer-redirect.js`).
- `catalog.json` — VHS tapes carry the identified play titles (see `tapes.json` for evidence).

Local test with production headers:  `python3 serve.py` → http://localhost:8766/

Deploy from this folder (needs `npx wrangler login` once; `wrangler.toml` = the project's current Cloudflare settings):
    npx wrangler pages deploy --project-name=fidibus-theater --branch=main
or upload the contents of `dist/` as a ZIP in the Cloudflare Pages dashboard (project fidibus-theater).
