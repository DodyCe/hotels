"""PostgreSQL privado por servicio; no usa la API pública ni Supabase Auth."""
import os
import sqlite3
from contextlib import contextmanager
from urllib.parse import parse_qs, unquote, urlsplit

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None

INTEGRITY_ERRORS = (sqlite3.IntegrityError,) + ((psycopg.IntegrityError,) if psycopg else ())
SETTINGS = {'auth': 'AUTH_DATABASE_URL', 'notifications': 'NOTIFICATIONS_DATABASE_URL'}
SCHEMAS = {'auth': 'hotels_auth', 'notifications': 'hotels_notifications'}


def database_url(name):
    return os.environ.get(SETTINGS.get(name, ''), '').strip()


def connection_identity(value):
    """Reconoce un proyecto incluso si se alterna conexión directa y pooler."""
    try:
        url = urlsplit(value)
        host = (url.hostname or '').lower()
        if url.scheme not in ('postgres', 'postgresql') or not host or not url.username or not url.path.strip('/'):
            raise ValueError()
        user = unquote(url.username)
        if host.startswith('db.') and host.endswith('.supabase.co'):
            return ('supabase', host.split('.')[1])
        if host.endswith('.pooler.supabase.com') and '.' in user:
            return ('supabase', user.rsplit('.', 1)[1])
        return (host, url.port or 5432, unquote(url.path))
    except (ValueError, TypeError):
        raise ValueError('La conexión debe ser una URL PostgreSQL válida; revisa el archivo .env.') from None


def validate_configuration(require_both=False):
    auth, notifications = (database_url(name) for name in SETTINGS)
    if require_both and not (auth and notifications):
        raise ValueError('Completa AUTH_DATABASE_URL y NOTIFICATIONS_DATABASE_URL en .env con dos proyectos distintos.')
    identities = [connection_identity(value) for value in (auth, notifications) if value]
    if len(identities) == 2 and identities[0] == identities[1]:
        raise ValueError('Autenticación y Notificaciones requieren bases distintas, no dos esquemas del mismo proyecto.')


class Database:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, parameters=()):
        # Solo SQL estático de estos dos servicios utiliza este adaptador.
        # Los valores siguen separados y enlazados por el driver.
        # Evita que extra_float_digits=0 redondee fechas Unix al leerlas como texto.
        return self.connection.execute(sql.replace('?', '%s'), parameters, binary=True)

    def executescript(self, script):
        # Los esquemas iniciales contienen únicamente sentencias CREATE simples.
        for statement in script.split(';'):
            if statement.strip():
                self.execute(statement)


@contextmanager
def connect(name):
    value = database_url(name)
    connection_identity(value)
    if psycopg is None:
        raise RuntimeError('Instala requirements.txt en el entorno Python para conectar con Supabase.')
    url = urlsplit(value)
    options = parse_qs(url.query)
    local = url.hostname in ('127.0.0.1', 'localhost', '::1')
    mode = options.get('sslmode', ['prefer' if local else 'require'])[-1]
    if not local and mode not in ('require', 'verify-ca', 'verify-full'):
        raise ValueError('Las bases remotas requieren TLS: usa sslmode=require o verify-full.')
    try:
        with psycopg.connect(value, connect_timeout=5, row_factory=dict_row, sslmode=mode) as connection:
            # Esquema constante elegido por código, nunca por datos de una petición.
            connection.execute('SET search_path TO ' + SCHEMAS[name] + ', pg_catalog')
            yield Database(connection)
    except psycopg.Error:
        # Los mensajes del driver pueden contener datos de conexión; no se registran.
        raise RuntimeError('No se pudo completar una operación PostgreSQL de ' + name + '; revisa conexión y migración.') from None


def initialize(name, db):
    """Valida la migración administrativa; el usuario de ejecución no puede hacer DDL."""
    owner = db.execute('SELECT service FROM hotels_meta.service_owner WHERE id=1').fetchone()
    if not owner or owner['service'] != name:
        raise ValueError('Esta base ya pertenece a otro microservicio. Selecciona otro proyecto de Supabase.')
    tables = ('users', 'sessions', 'outbox') if name == 'auth' else ('messages',)
    for table in tables:
        db.execute('SELECT 1 FROM ' + table + ' LIMIT 1')
