"""Punto de entrada HTTP. Sirve la web y enruta las APIs a procesos independientes."""
import json
import yaml
import os
import concurrent.futures
import hmac
import ipaddress
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
KEY = os.environ.get('INTERNAL_API_KEY', '')
ORIGIN_SECRET = os.environ.get('ORIGIN_SECRET','')
if len(KEY) < 32:
    raise RuntimeError('Usa start.py o configura INTERNAL_API_KEY.')
PORT = int(os.environ.get('GATEWAY_PORT') or os.environ.get('PORT', '8080'))
AUTH = os.environ.get('AUTH_URL', 'http://127.0.0.1:8101')
NOTIFICATIONS = os.environ.get('NOTIFICATIONS_URL', 'http://127.0.0.1:8102')
RESERVATIONS = os.environ.get('RESERVATIONS_URL', 'http://127.0.0.1:8103')
CATALOG = os.environ.get('CATALOG_URL', 'http://127.0.0.1:8104')
ROOMS = os.environ.get('ROOMS_URL', 'http://127.0.0.1:8105')
AVAILABILITY = os.environ.get('AVAILABILITY_URL', 'http://127.0.0.1:8106')
ORIGIN = os.environ.get('PUBLIC_ORIGIN', f'http://127.0.0.1:{PORT}').rstrip('/')
if os.environ.get('RENDER') == 'true':
    if len(ORIGIN_SECRET) < 32 or urlsplit(ORIGIN).scheme != 'https' or os.environ.get('GATEWAY_API_ONLY') != '1':
        raise RuntimeError('Render requiere ORIGIN_SECRET, PUBLIC_ORIGIN HTTPS y GATEWAY_API_ONLY=1.')
    if any(urlsplit(base).scheme != 'https' for base in (AUTH,NOTIFICATIONS,RESERVATIONS,CATALOG,ROOMS,AVAILABILITY)):
        raise RuntimeError('Configura las seis URLs HTTPS de los microservicios.')
ALLOWED_HOSTS = {f'127.0.0.1:{PORT}', f'localhost:{PORT}', urlsplit(ORIGIN).netloc}
if os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
    ALLOWED_HOSTS.add(os.environ['RENDER_EXTERNAL_HOSTNAME'])


def readiness():
    def healthy(item):
        name,base=item
        try:
            with urllib.request.urlopen(base+'/health',timeout=5) as response:
                return name,response.code==200 and json.load(response).get('status')=='ok'
        except (OSError,ValueError):
            return name,False
    services={'auth':AUTH,'notifications':NOTIFICATIONS,'reservations':RESERVATIONS,'catalog':CATALOG,'rooms':ROOMS,'availability':AVAILABILITY}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        result=dict(pool.map(healthy,services.items()))
    return {'ready':all(result.values()),'services':result}

class Gateway(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer' if urlsplit(self.path).path == '/reset-password.html' else 'strict-origin-when-cross-origin')
        if urlsplit(self.path).path == '/reset-password.html':
            self.send_header('Cache-Control','no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' https://images.unsplash.com data:; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
        super().end_headers()

    def error_json(self, status, message):
        body = json.dumps({'error': message}, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def respond_json(self, status, data):
        body=json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def handle_route(self):
        host = self.headers.get('Host', '')
        if host not in ALLOWED_HOSTS:
            return self.error_json(403, 'Host no permitido.')
        origin = self.headers.get('Origin')
        allowed_origins = {ORIGIN} if os.environ.get('RENDER') == 'true' else {ORIGIN,f'http://{host}'}
        if self.command != 'GET' and origin and origin not in allowed_origins:
            return self.error_json(403, 'Origen no permitido.')
        if self.command != 'GET' and self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.error_json(403, 'Solicitud externa no permitida.')
        path = urlsplit(self.path).path
        if ORIGIN_SECRET and (path.startswith('/api/') or path in ('/openapi.json','/openapi-internal.json')):
            if not hmac.compare_digest(self.headers.get('X-Origin-Secret',''),ORIGIN_SECRET):
                return self.error_json(403,'Acceso al Gateway requerido desde Hotels.')
        if path == '/api/readiness' and self.command == 'GET':
            return self.respond_json(200,readiness())
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
            if os.environ.get('GATEWAY_API_ONLY') == '1':
                return self.error_json(404,'Este servicio publica únicamente la API de Hotels.')
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
        client_ip = self.client_address[0]
        if ORIGIN_SECRET:
            try:
                client_ip=str(ipaddress.ip_address(self.headers.get('X-Real-IP','')))
            except ValueError:
                pass
        headers = {'X-Internal-Key': KEY, 'X-Client-IP': client_ip, 'Cookie': self.headers.get('Cookie', '')}
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
            return self.error_json(503, 'No se pudo conectar con los servicios. Espera un momento e intenta nuevamente.')
        with response:
            body = response.read()
            self.send_response(response.code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            for cookie in response.headers.get_all('Set-Cookie', []):
                self.send_header('Set-Cookie', cookie)
            if response.headers.get('Retry-After'):
                self.send_header('Retry-After',response.headers['Retry-After'])
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
