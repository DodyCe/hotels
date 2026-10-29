"""Autenticación: cuentas, scrypt, sesiones opacas y eventos de bienvenida."""
import hashlib
import os
import re
import secrets
import threading
import time
import uuid
import postgres
from urllib.parse import urlsplit
import validation
import account_security as security
from common import APIError, Handler, INTEGRITY_ERRORS, SESSION_SECONDS, connect, enqueue, init_outbox, serve, session_hash, start_outbox

with connect('auth') as db:
    if postgres.database_url('auth'):
        postgres.initialize('auth', db)
        db.execute('SELECT role,active FROM users LIMIT 1')
        db.execute('SELECT user_id,phone,active FROM guests LIMIT 1')
    else:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, salt TEXT NOT NULL, password_hash TEXT NOT NULL, created DOUBLE PRECISION NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires DOUBLE PRECISION NOT NULL);
        ''')
        init_outbox(db)
        columns = {r['name'] for r in db.execute('PRAGMA table_info(users)')}
        if 'role' not in columns:
            db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'guest'")
        if 'active' not in columns:
            db.execute('ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
        db.execute('''CREATE TABLE IF NOT EXISTS guests (
            id TEXT PRIMARY KEY, user_id TEXT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, phone TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1, created DOUBLE PRECISION NOT NULL)''')
        db.execute("INSERT OR IGNORE INTO guests(id,user_id,name,email,created) SELECT id,id,name,email,created FROM users")
        security.initialize_sqlite(db)
security.recovery_origin()

attempts, attempts_lock = {}, threading.Lock()

def password_hash(password, salt):
    return security.password_hash(password, salt)


def limit_client(handler, bucket='access', maximum=12):
    client = (bucket,handler.headers.get('X-Client-IP', handler.client_address[0]))
    with attempts_lock:
        now = time.time()
        for key in list(attempts):
            if not attempts[key] or now - attempts[key][-1] >= 60:
                attempts.pop(key)
        recent = [t for t in attempts.get(client, []) if now-t < 60]
        if len(recent) >= maximum:
            raise APIError(429, 'Demasiadas solicitudes. Espera un minuto.')
        attempts[client] = recent + [now]

def public_user(row):
    user = {key: row[key] for key in ('id', 'name', 'email')}
    if 'created' in row.keys():
        user['created'] = row['created']
    if 'role' in row.keys():
        user['role'] = row['role']
    return user

def current_user(handler):
    with connect('auth') as db:
        row = db.execute('SELECT u.id,u.name,u.email,u.created,u.role FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.active=1', (session_hash(handler), time.time())).fetchone()
    if not row:
        raise APIError(401, 'Inicia sesión para continuar.')
    return public_user(row)


def guest_data(row):
    return {key: (bool(row[key]) if key == 'active' else row[key]) for key in ('id','user_id','name','email','phone','active','created')}


def manage_guests(handler, path):
    administrator = current_user(handler)
    if administrator['role'] != 'admin':
        raise APIError(403, 'Se requiere una cuenta administradora.')
    identifier = path.removeprefix('/guests/').strip('/') if path != '/guests' else None
    if handler.command == 'GET' and identifier is None:
        with connect('auth') as db:
            rows = db.execute('SELECT * FROM guests ORDER BY created DESC,id').fetchall()
        return handler.respond(200, {'guests':[guest_data(r) for r in rows]})
    if handler.command == 'POST' and identifier is None:
        data = handler.body()
        name = validation.text(data.get('name'), 'El nombre', 80, 2)
        email = validation.email(data.get('email'))
        phone = validation.text(data.get('phone',''), 'El teléfono', 30, 0)
        identifier = str(uuid.uuid4())
        try:
            with connect('auth') as db:
                db.execute('INSERT INTO guests(id,name,email,phone,created) VALUES (?,?,?,?,?)', (identifier,name,email,phone,time.time()))
                row = db.execute('SELECT * FROM guests WHERE id=?',(identifier,)).fetchone()
        except INTEGRITY_ERRORS:
            raise APIError(409, 'Ya existe un huésped con ese correo.') from None
        return handler.respond(201, {'guest':guest_data(row)})
    if handler.command in ('PATCH','DELETE') and identifier:
        data = handler.body() if handler.command == 'PATCH' else {}
        if set(data) - {'name','email','phone','active'}:
            raise APIError(400, 'Solo se pueden modificar los datos del huésped.')
        try:
            with connect('auth') as db:
                row = db.execute('SELECT * FROM guests WHERE id=?',(identifier,)).fetchone()
                if not row:
                    raise APIError(404, 'Huésped no encontrado.')
                if row['user_id']:
                    owner = db.execute('SELECT role FROM users WHERE id=?',(row['user_id'],)).fetchone()
                    if owner['role'] == 'admin':
                        raise APIError(409, 'Las cuentas administradoras se gestionan por el operador, no como huéspedes.')
                    if 'email' in data and validation.email(data['email']) != row['email']:
                        raise APIError(409, 'El correo de una cuenta vinculada no se cambia desde administración.')
                name = validation.text(data.get('name',row['name']), 'El nombre',80,2)
                email = validation.email(data.get('email',row['email']))
                phone = validation.text(data.get('phone',row['phone']), 'El teléfono',30,0)
                enabled = 0 if handler.command == 'DELETE' else validation.active(data.get('active',bool(row['active'])))
                db.execute('UPDATE guests SET name=?,email=?,phone=?,active=? WHERE id=?',(name,email,phone,enabled,identifier))
                if row['user_id']:
                    db.execute('UPDATE users SET name=?,active=? WHERE id=?',(name,enabled,row['user_id']))
                    if not enabled:
                        db.execute('DELETE FROM sessions WHERE user_id=?',(row['user_id'],))
                row = db.execute('SELECT * FROM guests WHERE id=?',(identifier,)).fetchone()
        except INTEGRITY_ERRORS:
            raise APIError(409, 'Ya existe un huésped con ese correo.') from None
        return handler.respond(200, {'guest':guest_data(row)})
    raise APIError(405, 'Método no permitido para huéspedes.')

def session_cookie(token, max_age=SESSION_SECONDS):
    secure = '; Secure' if os.environ.get('COOKIE_SECURE') == '1' else ''
    return f'hotels_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={max_age}{secure}'

class Auth(Handler):
    service_name = 'autenticacion'
    database_name = 'auth'
    def route(self):
        path = urlsplit(self.path).path
        if path == '/guests' or path.startswith('/guests/'):
            return manage_guests(self,path)
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
        if self.command == 'POST' and self.path == '/auth/forgot-password':
            limit_client(self,'recovery',3)
            data = self.body()
            if set(data) != {'email'}:
                raise APIError(400, 'Indica únicamente el correo de tu cuenta.')
            return self.respond(202, security.request_recovery(validation.email(data['email'])))
        if self.command == 'POST' and self.path == '/auth/reset-password':
            limit_client(self,'reset',12)
            data = self.body()
            if set(data) != {'token','password','confirmPassword'}:
                raise APIError(400, 'Completa el enlace y la nueva contraseña dos veces.')
            password = data['password']
            if not isinstance(password,str) or not 10 <= len(password) <= 128:
                raise APIError(400, 'La contraseña debe tener entre 10 y 128 caracteres.')
            if data['confirmPassword'] != password:
                raise APIError(400, 'Las contraseñas no coinciden.')
            security.reset_password(data['token'],password)
            return self.respond(200, {'message':'Contraseña actualizada. Inicia sesión con tu nueva contraseña.'}, {'Set-Cookie':session_cookie('',0)})
        if self.command != 'POST' or self.path not in ('/auth/register', '/auth/login'):
            raise APIError(404, 'Ruta no encontrada.')
        limit_client(self)
        data = self.body()
        if set(data) - {'name','email','password'}:
            raise APIError(400, 'El registro no permite asignar roles ni permisos.')
        email, password = data.get('email', ''), data.get('password', '')
        if not isinstance(email, str) or not isinstance(password, str):
            raise APIError(400, 'Correo o contraseña inválidos.')
        email = email.strip().lower()
        if len(email) > 254 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', email) or '\r' in email or '\n' in email:
            raise APIError(400, 'Ingresa un correo válido.')
        registering = self.path.endswith('register')
        if not (10 if registering else 1) <= len(password) <= 128:
            raise APIError(400, 'La contraseña debe tener entre 10 y 128 caracteres.')
        if not registering:
            row, token, error = security.authenticate(email,password,session_hash(self))
            if error:
                status, body = error
                headers = {'Retry-After':str(body['retryAfterSeconds'])} if body.get('retryAfterSeconds') else None
                return self.respond(status,body,headers)
            return self.respond(200, {'user':public_user(row)}, {'Set-Cookie':session_cookie(token)})
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
                    db.execute('INSERT INTO users(id,name,email,salt,password_hash,created) VALUES (?,?,?,?,?,?)', (uid, name.strip(), email, salt, derived, time.time()))
                    profile = db.execute('SELECT id,active FROM guests WHERE email=?',(email,)).fetchone()
                    if profile and not profile['active']:
                        raise APIError(409, 'El registro de huésped está inactivo. Contacta con administración.')
                    if profile:
                        db.execute('UPDATE guests SET user_id=?,name=? WHERE id=?',(uid,name.strip(),profile['id']))
                    else:
                        db.execute('INSERT INTO guests(id,user_id,name,email,created) VALUES (?,?,?,?,?)',(uid,uid,name.strip(),email,time.time()))
                except INTEGRITY_ERRORS:
                    raise APIError(409, 'No se puede registrar esta cuenta. Intenta iniciar sesión.') from None
                row = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
                enqueue(db, {'id': 'welcome:' + uid, 'userId': uid, 'kind': 'welcome', 'payload': {}})
            db.execute('UPDATE login_security SET failed_attempts=0,window_started=0,locked_until=0 WHERE email_hash=?', (security.email_key(email),))
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires<=?', (time.time(),))
            # Rota la sesión presentada para evitar conservar la sesión anterior.
            db.execute('DELETE FROM sessions WHERE token_hash=?', (session_hash(self),))
            db.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['id'], time.time()+SESSION_SECONDS))
        self.respond(201 if registering else 200, {'user': public_user(row)}, {'Set-Cookie': session_cookie(token)})

if __name__ == '__main__':
    start_outbox('auth')
    serve(Auth, 8101)
