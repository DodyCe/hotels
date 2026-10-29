"""Autenticación: cuentas, scrypt, sesiones opacas y eventos de bienvenida."""
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
import uuid
import postgres
from common import APIError, Handler, INTEGRITY_ERRORS, SESSION_SECONDS, connect, enqueue, init_outbox, serve, session_hash, start_outbox

with connect('auth') as db:
    if postgres.database_url('auth'):
        postgres.initialize('auth', db)
    else:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, salt TEXT NOT NULL, password_hash TEXT NOT NULL, created DOUBLE PRECISION NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires DOUBLE PRECISION NOT NULL);
        ''')
        init_outbox(db)

attempts, attempts_lock = {}, threading.Lock()

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024, dklen=32).hex()

def public_user(row):
    user = {key: row[key] for key in ('id', 'name', 'email')}
    if 'created' in row.keys():
        user['created'] = row['created']
    return user

def current_user(handler):
    with connect('auth') as db:
        row = db.execute('SELECT u.id,u.name,u.email,u.created FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?', (session_hash(handler), time.time())).fetchone()
    if not row:
        raise APIError(401, 'Inicia sesión para continuar.')
    return public_user(row)

def session_cookie(token, max_age=SESSION_SECONDS):
    secure = '; Secure' if os.environ.get('COOKIE_SECURE') == '1' else ''
    return f'hotels_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={max_age}{secure}'

class Auth(Handler):
    service_name = 'autenticacion'
    database_name = 'auth'
    def route(self):
        if self.command == 'GET' and self.path == '/auth/me':
            return self.respond(200, {'user': current_user(self)})
        if self.command == 'GET' and self.path.startswith('/internal/users/'):
            identifier = self.path.removeprefix('/internal/users/')
            with connect('auth') as db:
                row = db.execute('SELECT id,name,email FROM users WHERE id=?', (identifier,)).fetchone()
            if not row:
                raise APIError(404, 'Usuario no encontrado.')
            return self.respond(200, {'user': public_user(row)})
        if self.command == 'POST' and self.path == '/auth/logout':
            with connect('auth') as db:
                db.execute('DELETE FROM sessions WHERE token_hash=?', (session_hash(self),))
            return self.respond(200, {'ok': True}, {'Set-Cookie': session_cookie('', 0)})
        if self.command != 'POST' or self.path not in ('/auth/register', '/auth/login'):
            raise APIError(404, 'Ruta no encontrada.')
        client = self.headers.get('X-Client-IP', self.client_address[0])
        with attempts_lock:
            now = time.time()
            # Limita también el tamaño del registro de intentos en memoria.
            for key in list(attempts):
                if not attempts[key] or now - attempts[key][-1] >= 60:
                    attempts.pop(key)
            recent = [t for t in attempts.get(client, []) if now-t < 60]
            if len(recent) >= 12:
                raise APIError(429, 'Demasiados intentos. Espera un minuto.')
            attempts[client] = recent + [now]
        data = self.body()
        email, password = data.get('email', ''), data.get('password', '')
        if not isinstance(email, str) or not isinstance(password, str):
            raise APIError(400, 'Correo o contraseña inválidos.')
        email = email.strip().lower()
        if len(email) > 254 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', email) or '\r' in email or '\n' in email:
            raise APIError(400, 'Ingresa un correo válido.')
        if not 10 <= len(password) <= 128:
            raise APIError(400, 'La contraseña debe tener entre 10 y 128 caracteres.')
        registering = self.path.endswith('register')
        with connect('auth') as db:
            row = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            if registering:
                name = data.get('name', '')
                if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
                    raise APIError(400, 'Ingresa un nombre de 2 a 80 caracteres.')
                if row:
                    raise APIError(409, 'No se puede registrar esta cuenta. Intenta iniciar sesión.')
                uid, salt = str(uuid.uuid4()), secrets.token_hex(16)
                derived = password_hash(password, salt)
                try:
                    db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)', (uid, name.strip(), email, salt, derived, time.time()))
                except INTEGRITY_ERRORS:
                    raise APIError(409, 'No se puede registrar esta cuenta. Intenta iniciar sesión.') from None
                row = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
                enqueue(db, {'id': 'welcome:' + uid, 'userId': uid, 'kind': 'welcome', 'payload': {}})
            else:
                salt = row['salt'] if row else '0'*32
                derived = password_hash(password, salt)
                if not row or not hmac.compare_digest(derived, row['password_hash']):
                    raise APIError(401, 'Correo o contraseña incorrectos.')
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires<=?', (time.time(),))
            # Rota la sesión presentada para evitar conservar la sesión anterior.
            db.execute('DELETE FROM sessions WHERE token_hash=?', (session_hash(self),))
            db.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['id'], time.time()+SESSION_SECONDS))
        self.respond(201 if registering else 200, {'user': public_user(row)}, {'Set-Cookie': session_cookie(token)})

if __name__ == '__main__':
    start_outbox('auth')
    serve(Auth, 8101)
