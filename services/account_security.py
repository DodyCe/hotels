"""Bloqueo por correo y recuperación de contraseña, propiedad exclusiva de Auth."""
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import time
from urllib.parse import urlsplit

import postgres
from common import APIError, SESSION_SECONDS, connect, enqueue

MAX_FAILURES = 6
LOCK_SECONDS = 15 * 60
RESET_SECONDS = 15 * 60
RESET_COOLDOWN = 60
RECOVERY_MESSAGE = 'Si existe una cuenta activa con ese correo, recibirás un enlace para restablecer tu contraseña. Revisa también la carpeta de spam.'


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64*1024*1024, dklen=32).hex()


def email_key(email):
    return hashlib.sha256(email.encode()).hexdigest()


def recovery_origin():
    origin = os.environ.get('PUBLIC_ORIGIN', 'http://127.0.0.1:8080').rstrip('/')
    parsed = urlsplit(origin)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
            or parsed.scheme not in ('http','https')
            or (parsed.scheme == 'http' and parsed.hostname not in ('127.0.0.1','localhost','::1'))):
        raise ValueError('PUBLIC_ORIGIN requiere HTTPS; HTTP solo se permite en localhost.')
    return origin


def initialize_sqlite(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS login_security (
            email_hash TEXT PRIMARY KEY,
            failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK(failed_attempts BETWEEN 0 AND 6),
            window_started DOUBLE PRECISION NOT NULL DEFAULT 0,
            locked_until DOUBLE PRECISION NOT NULL DEFAULT 0,
            reset_requested_at DOUBLE PRECISION NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS password_resets (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            created DOUBLE PRECISION NOT NULL, expires DOUBLE PRECISION NOT NULL);
    ''')


def lock_account(db, key):
    if not postgres.database_url('auth'):
        db.execute('BEGIN IMMEDIATE')
    # UPSERT bloquea la fila también cuando dos instancias crean el contador a la vez.
    return db.execute('INSERT INTO login_security(email_hash) VALUES (?) ON CONFLICT(email_hash) DO UPDATE SET email_hash=excluded.email_hash RETURNING *', (key,)).fetchone()


def cleanup_expired(db):
    now = time.time()
    db.execute('DELETE FROM password_resets WHERE expires<=?', (now,))
    db.execute('DELETE FROM login_security WHERE window_started<? AND locked_until<? AND reset_requested_at<?',
               (now-LOCK_SECONDS,now-LOCK_SECONDS,now-LOCK_SECONDS))


def locked_error(until, now):
    retry = max(1, math.ceil(until - now))
    return (429, {'error':f'Acceso bloqueado por demasiadas contraseñas incorrectas. Inténtalo en {math.ceil(retry/60)} minutos o recupera tu contraseña.',
                  'attemptsRemaining':0, 'lockedUntil':until, 'retryAfterSeconds':retry})


def authenticate(email, password, previous_session):
    """La sesión y el contador cambian en la misma transacción serializada por correo."""
    key = email_key(email)
    with connect('auth') as db:
        state = lock_account(db, key)
        now = time.time()
        if state['locked_until'] > now:
            return None, None, locked_error(state['locked_until'], now)
        row = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        derived = password_hash(password, row['salt'] if row else '0'*32)
        if not row or not hmac.compare_digest(derived, row['password_hash']):
            recent = state['window_started'] > now - LOCK_SECONDS and not state['locked_until']
            failures = state['failed_attempts'] + 1 if recent else 1
            until = now + LOCK_SECONDS if failures == MAX_FAILURES else 0
            db.execute('UPDATE login_security SET failed_attempts=?,window_started=?,locked_until=? WHERE email_hash=?',
                       (failures,state['window_started'] if recent else now,until,key))
            error = locked_error(until,now) if until else (401,{
                'error':f'Correo o contraseña incorrectos. Te quedan {MAX_FAILURES-failures} intentos antes del bloqueo temporal.',
                'attemptsRemaining':MAX_FAILURES-failures, 'lockedUntil':None, 'retryAfterSeconds':0})
            return None, None, error
        if not row['active']:
            return None, None, (403, {'error':'Esta cuenta está inactiva. Contacta con administración.'})
        db.execute('UPDATE login_security SET failed_attempts=0,window_started=0,locked_until=0 WHERE email_hash=?', (key,))
        token = secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<=? OR token_hash=?', (now,previous_session))
        db.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(),row['id'],now+SESSION_SECONDS))
        return row, token, None


def request_recovery(email):
    key = email_key(email)
    with connect('auth') as db:
        state = lock_account(db, key)
        now = time.time()
        if state['reset_requested_at'] > now - RESET_COOLDOWN:
            return {'message':RECOVERY_MESSAGE}
        db.execute('UPDATE login_security SET reset_requested_at=? WHERE email_hash=?', (now,key))
        row = db.execute('SELECT id FROM users WHERE email=? AND active=1', (email,)).fetchone()
        uid = row['id'] if row else None
        # Mismo trabajo y número de consultas para direcciones existentes e inexistentes.
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        db.execute('DELETE FROM password_resets WHERE user_id=? OR expires<=?', (uid,now))
        db.execute('INSERT INTO password_resets(token_hash,user_id,created,expires) SELECT ?,id,?,? FROM users WHERE id=? AND active=1',
                   (digest,now,now+RESET_SECONDS,uid))
        event = {'id':'password-reset:'+(uid or 'unknown')+':'+secrets.token_hex(16), 'userId':uid, 'kind':'password.reset',
                 'payload':{'resetUrl':recovery_origin()+'/reset-password.html#token='+token, 'expiresAt':now+RESET_SECONDS}}
        db.execute('INSERT INTO outbox(id,body) SELECT ?,? WHERE CAST(? AS TEXT) IS NOT NULL', (event['id'],json.dumps(event),uid))
        # Datos efímeros caducados, sin correos legibles ni cuentas eliminadas.
        db.execute('DELETE FROM login_security WHERE window_started<? AND locked_until<? AND reset_requested_at<?',
                   (now-LOCK_SECONDS,now-LOCK_SECONDS,now-LOCK_SECONDS))
    return {'message':RECOVERY_MESSAGE}


def reset_password(token, password):
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise APIError(400, 'El enlace no es válido o ya venció. Solicita uno nuevo.')
    digest = hashlib.sha256(token.encode()).hexdigest()
    with connect('auth') as db:
        selected = db.execute('SELECT u.email FROM password_resets r JOIN users u ON u.id=r.user_id WHERE r.token_hash=?', (digest,)).fetchone()
    if not selected:
        raise APIError(400, 'El enlace no es válido o ya venció. Solicita uno nuevo.')
    key = email_key(selected['email'])
    with connect('auth') as db:
        lock_account(db, key)
        row = db.execute('SELECT r.user_id FROM password_resets r JOIN users u ON u.id=r.user_id WHERE r.token_hash=? AND r.expires>? AND u.active=1', (digest,time.time())).fetchone()
        if not row:
            raise APIError(400, 'El enlace no es válido o ya venció. Solicita uno nuevo.')
        salt = secrets.token_hex(16)
        db.execute('UPDATE users SET salt=?,password_hash=? WHERE id=?', (salt,password_hash(password,salt),row['user_id']))
        db.execute('DELETE FROM sessions WHERE user_id=?', (row['user_id'],))
        db.execute('DELETE FROM password_resets WHERE user_id=?', (row['user_id'],))
        db.execute('UPDATE login_security SET failed_attempts=0,window_started=0,locked_until=0 WHERE email_hash=?', (key,))
        enqueue(db, {'id':'password-changed:'+row['user_id']+':'+secrets.token_hex(16), 'userId':row['user_id'], 'kind':'password.changed', 'payload':{}})
