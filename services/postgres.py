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
SETTINGS = {'auth': 'AUTH_DATABASE_URL', 'notifications': 'NOTIFICATIONS_DATABASE_URL',
            'catalog': 'CATALOG_DATABASE_URL', 'rooms': 'ROOMS_DATABASE_URL',
            'reservations': 'RESERVATIONS_DATABASE_URL', 'availability': 'AVAILABILITY_DATABASE_URL'}
SCHEMAS = {name: 'hotels_' + name for name in SETTINGS}
TABLES = {'auth': ('users', 'sessions', 'outbox', 'guests', 'login_security', 'password_resets'), 'notifications': ('messages',),
          'catalog': ('hotels',), 'rooms': ('rooms',),
          'reservations': ('reservations', 'outbox'), 'availability': ('inventory', 'allocations')}


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


def validate_configuration(require_both=False, require_services=()):
    required = set(require_services) | ({'auth', 'notifications'} if require_both else set())
    if not required <= SETTINGS.keys():
        raise ValueError('Microservicio PostgreSQL desconocido.')
    if any(not database_url(name) for name in required):
        raise ValueError('Completa las conexiones PostgreSQL requeridas en .env con proyectos distintos.')
    identities = [connection_identity(database_url(name)) for name in SETTINGS if database_url(name)]
    if len(identities) != len(set(identities)):
        raise ValueError('Los microservicios requieren bases distintas, no varios esquemas del mismo proyecto.')


class Database:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, parameters=()):
        # Solo SQL estático de los servicios configurados utiliza este adaptador.
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
            if name in ('reservations','availability'):
                connection.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
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
    for table in TABLES[name]:
        db.execute('SELECT 1 FROM ' + table + ' LIMIT 1')
