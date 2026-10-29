"""Utilidades HTTP y outbox. Cada servicio conserva su propia base de datos."""
import hashlib
import datetime as dt
import hmac
import json
import logging
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import postgres

INTEGRITY_ERRORS = postgres.INTEGRITY_ERRORS

KEY = os.environ.get('INTERNAL_API_KEY', '')
if len(KEY) < 32:
    raise RuntimeError('INTERNAL_API_KEY debe contener al menos 32 caracteres; usa start.py.')
DATA = Path(os.environ.get('HOTELS_DATA_DIR', str(Path(__file__).resolve().parents[1] / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
AUTH = os.environ.get('AUTH_URL', 'http://127.0.0.1:8101')
NOTIFICATIONS = os.environ.get('NOTIFICATIONS_URL', 'http://127.0.0.1:8102')
CATALOG = os.environ.get('CATALOG_URL', 'http://127.0.0.1:8104')
ROOMS = os.environ.get('ROOMS_URL', 'http://127.0.0.1:8105')
AVAILABILITY = os.environ.get('AVAILABILITY_URL', 'http://127.0.0.1:8106')
SESSION_SECONDS = 8 * 60 * 60
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def validate_dates(arrival, departure, allow_past=False):
    try:
        a, b = dt.date.fromisoformat(arrival), dt.date.fromisoformat(departure)
        today = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).date()
        if a.isoformat() != arrival or b.isoformat() != departure or (a < today and not allow_past) or not 1 <= (b-a).days <= 30:
            raise ValueError()
        return a, b
    except (ValueError, TypeError):
        raise APIError(400, 'Selecciona fechas AAAA-MM-DD desde hoy, con una estancia de 1 a 30 noches.') from None

@contextmanager
def connect(name):
    if postgres.database_url(name):
        with postgres.connect(name) as db:
            yield db
        return
    if os.environ.get('RENDER') == 'true':
        raise RuntimeError('El despliegue requiere la conexión PostgreSQL propia del microservicio.')
    db = sqlite3.connect(DATA / (name + '.sqlite3'), timeout=15)
    try:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA foreign_keys=ON')
        with db:
            yield db
    finally:
        db.close()

def internal_request(base, path, body=None, cookie=''):
    headers = {'X-Internal-Key': KEY, 'Cookie': cookie}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=headers), timeout=8) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            message = json.load(error).get('error', 'Error del servicio')
        except (ValueError, AttributeError):
            message = 'Error del servicio'
        raise APIError(error.code, message) from None
    except (OSError, TimeoutError):
        raise APIError(503, 'Un servicio no está disponible. Intenta nuevamente.') from None

def user_for(handler):
    return internal_request(AUTH, '/auth/me', cookie=handler.headers.get('Cookie', ''))['user']


def admin_for(handler):
    user = user_for(handler)
    if user.get('role') != 'admin':
        raise APIError(403, 'Se requiere una cuenta administradora.')
    return user

def session_hash(handler):
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get('Cookie', ''))
        token = cookie.get('hotels_session')
        if not token or len(token.value) > 200:
            return ''
        return hashlib.sha256(token.value.encode()).hexdigest()
    except Exception:
        return ''

def init_outbox(db):
    db.execute('CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, body TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_try DOUBLE PRECISION NOT NULL DEFAULT 0, delivered INTEGER NOT NULL DEFAULT 0)')

def enqueue(db, event):
    db.execute('INSERT INTO outbox(id, body) VALUES (?, ?) ON CONFLICT(id) DO NOTHING', (event['id'], json.dumps(event)))

def start_outbox(name):
    def worker():
        last_cleanup = 0
        while True:
            try:
                with connect(name) as db:
                    if name == 'auth' and time.time()-last_cleanup >= 60:
                        from account_security import cleanup_expired
                        cleanup_expired(db)
                        last_cleanup = time.time()
                    rows = db.execute('SELECT * FROM outbox WHERE delivered=0 AND next_try<=? ORDER BY next_try,id LIMIT 10', (time.time(),)).fetchall()
                for row in rows:
                    try:
                        event = json.loads(row['body'])
                        expired = name == 'auth' and row['id'].startswith('password-reset:') and event['payload']['expiresAt']<=time.time()
                        if not expired:
                            internal_request(NOTIFICATIONS, '/internal/events', event)
                        with connect(name) as db:
                            db.execute('UPDATE outbox SET delivered=1 WHERE id=?', (row['id'],))
                            if name == 'auth' and row['id'].startswith('password-reset:'):
                                db.execute("UPDATE outbox SET body='{}' WHERE id=?", (row['id'],))
                    except APIError:
                        with connect(name) as db:
                            db.execute('UPDATE outbox SET attempts=attempts+1,next_try=? WHERE id=?', (time.time() + min(60, 2 ** min(row['attempts'] + 1, 6)), row['id']))
            except Exception:
                logging.exception('Error procesando outbox de %s', name)
            time.sleep(1)
    threading.Thread(target=worker, daemon=True).start()

class Handler(BaseHTTPRequestHandler):
    server_version = 'Hotels/1.0'
    def health(self):
        name = getattr(self, 'database_name', None)
        if name:
            try:
                with connect(name) as db:
                    db.execute('SELECT 1').fetchone()
            except Exception:
                return self.respond(503, {'status': 'unavailable', 'service': self.service_name})
            return self.respond(200, {'status': 'ok', 'service': self.service_name,
                                     'database': 'postgresql' if postgres.database_url(name) else 'sqlite'})
        return self.respond(200, {'status': 'ok', 'service': self.service_name})
    def log_message(self, fmt, *args):
        # No registrar cuerpos, cookies, contraseñas o direcciones de correo.
        logging.info('%s %s %s', self.command, self.path.split('?')[0], args[1] if len(args) > 1 else '')

    def body(self):
        if self.headers.get_content_type() != 'application/json':
            raise APIError(415, 'Se requiere application/json.')
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise APIError(413, 'Solicitud vacía o demasiado grande.')
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, UnicodeError):
            raise APIError(400, 'JSON inválido.') from None

    def respond(self, status, data, headers=None):
        content = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(content)

    def handle_request(self):
        try:
            if self.path == '/health' and self.command == 'GET':
                return self.health()
            supplied = self.headers.get('X-Internal-Key', '')
            if not hmac.compare_digest(supplied, KEY):
                raise APIError(403, 'Acceso interno requerido.')
            self.route()
        except APIError as error:
            self.respond(error.status, {'error': error.message})
        except Exception:
            logging.exception('Error interno en %s', self.service_name)
            self.respond(500, {'error': 'Error interno del servicio.'})

    do_GET = handle_request
    do_POST = handle_request
    do_DELETE = handle_request
    do_PUT = handle_request
    do_PATCH = handle_request

def serve(handler, port):
    address = os.environ.get('SERVICE_BIND', '127.0.0.1')
    server = ThreadingHTTPServer((address, int(os.environ.get('PORT', port))), handler)
    server.daemon_threads = True
    logging.info('%s listo en %s:%s', handler.service_name, address, server.server_port)
    server.serve_forever()
