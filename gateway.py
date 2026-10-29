"""Punto de entrada HTTP. Sirve la web y enruta las APIs a procesos independientes."""
import json
import yaml
import os
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
KEY = os.environ.get('INTERNAL_API_KEY', '')
if len(KEY) < 32:
    raise RuntimeError('Usa start.py o configura INTERNAL_API_KEY.')
PORT = int(os.environ.get('GATEWAY_PORT', '8080'))
AUTH = os.environ.get('AUTH_URL', 'http://127.0.0.1:8101')
NOTIFICATIONS = os.environ.get('NOTIFICATIONS_URL', 'http://127.0.0.1:8102')
RESERVATIONS = os.environ.get('RESERVATIONS_URL', 'http://127.0.0.1:8103')
CATALOG = os.environ.get('CATALOG_URL', 'http://127.0.0.1:8104')
ROOMS = os.environ.get('ROOMS_URL', 'http://127.0.0.1:8105')
AVAILABILITY = os.environ.get('AVAILABILITY_URL', 'http://127.0.0.1:8106')
ORIGIN = os.environ.get('PUBLIC_ORIGIN', f'http://127.0.0.1:{PORT}').rstrip('/')
ALLOWED_HOSTS = {f'127.0.0.1:{PORT}', f'localhost:{PORT}', urlsplit(ORIGIN).netloc}

class Gateway(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' https://images.unsplash.com data:; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
        super().end_headers()

    def error_json(self, status, message):
        body = json.dumps({'error': message}, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def handle_route(self):
        host = self.headers.get('Host', '')
        if host not in ALLOWED_HOSTS:
            return self.error_json(403, 'Host no permitido.')
        origin = self.headers.get('Origin')
        if self.command != 'GET' and origin and origin not in (ORIGIN, f'http://{host}'):
            return self.error_json(403, 'Origen no permitido.')
        if self.command != 'GET' and self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.error_json(403, 'Solicitud externa no permitida.')
        path = urlsplit(self.path).path
        if self.command == 'GET' and path in ('/openapi.json','/openapi-internal.json'):
            filename = 'internal-openapi.yaml' if path == '/openapi-internal.json' else 'openapi.yaml'
            body = json.dumps(yaml.safe_load((ROOT/'docs'/filename).read_text(encoding='utf-8')),ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if self.command == 'GET' and path == '/vendor/swagger-ui-bundle.js':
            body = (ROOT/'web'/'vendor'/'swagger-ui-bundle.js.gz').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type','text/javascript; charset=utf-8')
            self.send_header('Content-Encoding','gzip')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if path == '/health' and self.command == 'GET':
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(b'{"status":"ok","service":"gateway"}'); return
        if not path.startswith('/api/'):
            if self.command != 'GET':
                return self.error_json(405, 'Método no permitido.')
            if any(part.startswith('.') for part in unquote(path).split('/') if part):
                return self.error_json(404, 'Archivo no encontrado.')
            return super().do_GET()
        route = self.path.removeprefix('/api')
        if path.startswith('/api/auth/') or path == '/api/guests' or path.startswith('/api/guests/'):
            base = AUTH
        elif path == '/api/notifications':
            base = NOTIFICATIONS
        elif path == '/api/reservations' or path.startswith('/api/reservations/'):
            base = RESERVATIONS
        elif path == '/api/hotels' or path.startswith('/api/hotels/'):
            base = CATALOG
        elif path == '/api/rooms' or path.startswith('/api/rooms/'):
            base = ROOMS
        elif path in ('/api/availability','/api/inventory') or path.startswith('/api/inventory/'):
            base = AVAILABILITY
        else:
            return self.error_json(404, 'Ruta no encontrada.')
        payload = None
        headers = {'X-Internal-Key': KEY, 'X-Client-IP': self.client_address[0], 'Cookie': self.headers.get('Cookie', '')}
        if self.command in ('POST','PATCH','PUT'):
            if self.headers.get_content_type() != 'application/json':
                return self.error_json(415, 'Se requiere application/json.')
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384:
                    return self.error_json(413, 'Solicitud vacía o demasiado grande.')
            except ValueError:
                return self.error_json(400, 'Longitud inválida.')
            payload = self.rfile.read(length)
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(base + route, data=payload, headers=headers, method=self.command)
        try:
            response = urllib.request.urlopen(request, timeout=12)
        except urllib.error.HTTPError as error:
            response = error
        except (OSError, TimeoutError):
            return self.error_json(503, 'No se pudo conectar con los servicios. Inicia la aplicación con INICIAR.cmd.')
        with response:
            body = response.read()
            self.send_response(response.code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            for cookie in response.headers.get_all('Set-Cookie', []):
                self.send_header('Set-Cookie', cookie)
            self.end_headers(); self.wfile.write(body)

    do_GET = handle_route
    do_POST = handle_route
    do_PATCH = handle_route
    do_PUT = handle_route
    do_DELETE = handle_route

if __name__ == '__main__':
    server = ThreadingHTTPServer((os.environ.get('GATEWAY_BIND', '127.0.0.1'), PORT), partial(Gateway, directory=str(ROOT / 'web')))
    server.daemon_threads = True
    print(f'Hotels disponible en {ORIGIN}', flush=True)
    server.serve_forever()
