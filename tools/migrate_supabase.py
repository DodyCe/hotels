"""Comprueba bases independientes; --apply copia SQLite sin sobrescribir datos."""
import argparse
import json
import os
import socket
import sqlite3
import sys
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'services'))
from start import load_environment
import postgres

# Clave primaria, columnas inmutables que deben coincidir en los reintentos.
TABLES = {
    'auth': {'users': ('id', ('id', 'name', 'email', 'salt', 'password_hash', 'created')),
             'sessions': ('token_hash', ('token_hash', 'user_id', 'expires')),
             'outbox': ('id', ('id', 'body'))},
    'notifications': {'messages': ('id', ('id', 'user_id', 'recipient', 'subject', 'body', 'created'))},
    'catalog': {'hotels': ('id', ('id', 'document', 'sort_order'))},
    'rooms': {'rooms': ('id', ('id', 'hotelId', 'name', 'capacity', 'price', 'sort_order'))}
}


def snapshot_sources(directory, backup=False, services=None):
    snapshots = {}
    folder = directory / 'backups' / ('supabase-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    for name, tables in TABLES.items():
        if services is not None and name not in services:
            continue
        source = directory / (name + '.sqlite3')
        snapshots[name] = {}
        if not source.exists():
            continue
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            if backup:
                folder.mkdir(parents=True, exist_ok=True)
                with closing(sqlite3.connect(folder / source.name)) as target:
                    db.backup(target)
            for table in tables:
                if db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', table)).fetchone():
                    query = 'SELECT * FROM ' + table
                    parameters = ()
                    if table == 'sessions':
                        query += ' WHERE expires>?'
                        parameters = (time.time(),)
                    if name in ('catalog', 'rooms'):
                        query += ' ORDER BY rowid'
                    rows = [dict(row) for row in db.execute(query, parameters)]
                    if name in ('catalog', 'rooms'):
                        for position, row in enumerate(rows):
                            row['sort_order'] = position
                    snapshots[name][table] = rows
    return snapshots


def inspect_rows(name, source, db, apply=False):
    report = {}
    for table, (key, immutable) in TABLES[name].items():
        rows = source.get(table, [])
        pending = 0
        for row in rows:
            existing = db.execute('SELECT * FROM ' + table + ' WHERE ' + key + '=?', (row[key],)).fetchone()
            if existing:
                if any(existing[column] != row[column] for column in immutable):
                    raise ValueError('Hay un conflicto de datos en ' + name + '.' + table + '; no se sobrescribirá.')
                continue
            pending += 1
            if apply:
                columns = tuple(row)
                if any(column not in ALLOWED_COLUMNS[table] for column in columns):
                    raise ValueError('El esquema SQLite no es compatible con la migración.')
                db.execute('INSERT INTO ' + table + '(' + ','.join('"'+column+'"' for column in columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')', tuple(row[c] for c in columns))
        total = db.execute('SELECT COUNT(*) AS total FROM ' + table).fetchone()['total']
        report[table] = {'sqlite': len(rows), 'postgresql': total, 'copiados' if apply else 'pendientes': pending}
    return report


ALLOWED_COLUMNS = {
    'users': {'id', 'name', 'email', 'salt', 'password_hash', 'created'},
    'sessions': {'token_hash', 'user_id', 'expires'},
    'outbox': {'id', 'body', 'attempts', 'next_try', 'delivered'},
    'messages': {'id', 'user_id', 'recipient', 'subject', 'body', 'status', 'created', 'attempts', 'next_try'},
    'hotels': {'id', 'document', 'sort_order'},
    'rooms': {'id', 'hotelId', 'name', 'capacity', 'price', 'sort_order'}
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Respalda y copia las filas; detén Hotels antes de ejecutarlo.')
    parser.add_argument('--services', nargs='+', choices=tuple(TABLES), default=['auth', 'notifications'],
                        help='Servicios a copiar; por defecto Auth y Notificaciones.')
    options = parser.parse_args()
    load_environment()
    postgres.validate_configuration(require_services=options.services)
    if options.apply:
        ports = {'auth':8101, 'notifications':8102, 'catalog':8104, 'rooms':8105}
        for port in (8080, *(ports[name] for name in options.services)):
            try:
                probe = socket.create_connection(('127.0.0.1', port), timeout=.3)
            except OSError:
                continue
            probe.close()
            raise ValueError('Detén Hotels con Ctrl+C antes de migrar sus bases.')
    directory = Path(os.environ.get('HOTELS_DATA_DIR', str(ROOT / 'data'))).resolve()
    sources = snapshot_sources(directory, backup=options.apply, services=options.services)
    reports = {}
    # Preflight de ambos destinos antes de copiar la primera fila.
    for name in options.services:
        with postgres.connect(name) as db:
            postgres.initialize(name, db)
            owner = db.execute('SELECT service FROM hotels_meta.service_owner WHERE id=1').fetchone()
            if not owner or owner['service'] != name:
                raise ValueError('La base configurada no pertenece a ' + name + '.')
            reports[name] = inspect_rows(name, sources[name], db)
    if options.apply:
        for name in options.services:
            with postgres.connect(name) as db:
                reports[name] = inspect_rows(name, sources[name], db, apply=True)
    print(json.dumps({'mode': 'apply' if options.apply else 'check', 'services': reports}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print('No se pudo comprobar o copiar la información. Revisa conexión, tablas y respaldo local.', file=sys.stderr)
        sys.exit(1)
