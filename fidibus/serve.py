#!/usr/bin/env python3
"""Serve the concept prototypes locally.

Static files come from this folder; /media/* is proxied (with Range support) to the
live archive, because fidibus.munzel.com sends Cross-Origin-Resource-Policy: same-origin
and the browser would refuse to embed the videos from another origin.

    python3 serve.py            # http://localhost:8765/
"""
import shutil, sys, urllib.request, urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ORIGIN = 'https://fidibus.munzel.com'
CSP = next(l.split(':', 1)[1].strip() for l in (Path(__file__).parent / 'dist/_headers').read_text().splitlines() if 'Content-Security-Policy' in l)
PASS = ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges', 'Last-Modified', 'ETag')


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(Path(__file__).parent / 'dist'), **kw)

    def _proxy(self, head=False):
        req = urllib.request.Request(ORIGIN + self.path, method='HEAD' if head else 'GET',
                                     headers={'User-Agent': 'Mozilla/5.0 fidibus-concepts'})  # CF rejects urllib's UA
        if 'Range' in self.headers:
            req.add_header('Range', self.headers['Range'])
        try:
            up = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            up = e
        self.send_response(up.status if hasattr(up, 'status') else up.code)
        for k in PASS:
            if up.headers.get(k):
                self.send_header(k, up.headers[k])
        self.end_headers()
        if not head:
            try:
                shutil.copyfileobj(up, self.wfile, 256 * 1024)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser cancels range requests all the time while seeking

    def do_GET(self):
        if self.path.startswith('/media/'):
            return self._proxy()
        return super().do_GET()

    def do_HEAD(self):
        if self.path.startswith('/media/'):
            return self._proxy(head=True)
        return super().do_HEAD()

    def end_headers(self):
        # same security headers as production (dist/_headers), so CSP problems show up locally
        self.send_header('Content-Security-Policy', CSP)
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    print(f'http://localhost:{port}/')
    ThreadingHTTPServer(('', port), Handler).serve_forever()
