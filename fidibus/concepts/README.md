# Fidibus – three interface concepts

Working prototypes against the real catalog (`catalog.json`, posters copied from the live site).
Videos stream from fidibus.munzel.com through `serve.py`, because the live site sends
`Cross-Origin-Resource-Policy: same-origin`.

    python3 serve.py   # → http://localhost:8765/

1. `1-papiertheater.html` – toy theatre: tags on a rope, curtain + painted backdrop, footlights = timeline
2. `2-videorekorder.html` – living room: VHS shelf, CRT, VCR with picture search, remote index search
3. `3-litfasssaeule.html` – advertising column of posters → tear ticket → auditorium with seat-dependent view
