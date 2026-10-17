"""Inventario propio y ocupación por noche. Asignación y liberación idempotentes."""
import datetime as dt
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from common import APIError, Handler, connect, serve, validate_dates

seed = json.loads((Path(__file__).resolve().parents[1] / 'seed' / 'inventory.json').read_text(encoding='utf-8'))
with connect('availability') as db:
    db.executescript('''
    CREATE TABLE IF NOT EXISTS inventory (room_id TEXT PRIMARY KEY, total INTEGER NOT NULL CHECK(total>=1));
    CREATE TABLE IF NOT EXISTS allocations (reservation_id TEXT PRIMARY KEY, room_id TEXT NOT NULL DEFAULT '', checkin TEXT NOT NULL DEFAULT '', checkout TEXT NOT NULL DEFAULT '', status TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS allocation_dates ON allocations(room_id,status,checkin,checkout);
    ''')
    db.executemany('INSERT OR IGNORE INTO inventory VALUES (:roomId,:total)', seed)

def available_units(db, room_id, start, end):
    row = db.execute('SELECT total FROM inventory WHERE room_id=?', (room_id,)).fetchone()
    if not row:
        raise APIError(404, 'Habitación no registrada en el inventario.')
    result = row['total']
    day = start
    while day < end:
        occupied = db.execute("SELECT count(*) FROM allocations WHERE room_id=? AND status='Asignada' AND checkin<=? AND checkout>?", (room_id, day.isoformat(), day.isoformat())).fetchone()[0]
        result = min(result, row['total']-occupied)
        day += dt.timedelta(days=1)
    return max(0, result)

def validate_id(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 160:
        raise APIError(400, 'Identificador de reserva inválido.')
    return value

class Availability(Handler):
    service_name = 'disponibilidad-inventario'
    def route(self):
        url = urlsplit(self.path)
        if self.command == 'GET' and url.path == '/inventory':
            with connect('availability') as db:
                rows = db.execute('SELECT room_id AS roomId,total FROM inventory ORDER BY rowid').fetchall()
            return self.respond(200, {'inventory': [dict(r) for r in rows]})
        if self.command == 'GET' and url.path == '/availability':
            query = parse_qs(url.query)
            a, b = validate_dates(query.get('checkin', [''])[0], query.get('checkout', [''])[0])
            with connect('availability') as db:
                rows = db.execute('SELECT room_id,total FROM inventory ORDER BY rowid').fetchall()
                result = [{'roomId':r['room_id'],'total':r['total'],'available':available_units(db,r['room_id'],a,b)} for r in rows]
            return self.respond(200, {'availability': result})
        if self.command == 'POST' and url.path == '/internal/allocate':
            data = self.body()
            rid = validate_id(data.get('reservationId'))
            # Permite recuperar reservas antiguas ya validadas por Reservas.
            a, b = validate_dates(data.get('checkin'), data.get('checkout'), allow_past=True)
            room = data.get('roomId')
            if not isinstance(room, str):
                raise APIError(400, 'Habitación inválida.')
            with connect('availability') as db:
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT * FROM allocations WHERE reservation_id=?', (rid,)).fetchone()
                if existing:
                    if existing['status'] == 'Liberada':
                        raise APIError(409, 'La reserva ya fue liberada y no puede reactivarse.')
                    if (existing['room_id'],existing['checkin'],existing['checkout']) != (room,a.isoformat(),b.isoformat()):
                        raise APIError(409, 'El identificador ya corresponde a otra asignación.')
                    return self.respond(200, {'allocated': True, 'duplicate': True})
                if available_units(db,room,a,b) < 1:
                    raise APIError(409, 'La habitación de práctica no tiene cupos para esas fechas.')
                db.execute('INSERT INTO allocations VALUES (?,?,?,?,?)', (rid,room,a.isoformat(),b.isoformat(),'Asignada'))
            return self.respond(201, {'allocated': True})
        if self.command == 'POST' and url.path == '/internal/release':
            rid = validate_id(self.body().get('reservationId'))
            with connect('availability') as db:
                db.execute('BEGIN IMMEDIATE')
                # Una liberación desconocida deja una marca que impide asignaciones tardías.
                db.execute("INSERT INTO allocations(reservation_id,status) VALUES (?,'Liberada') ON CONFLICT(reservation_id) DO UPDATE SET status='Liberada'", (rid,))
            return self.respond(200, {'released': True})
        raise APIError(404, 'Ruta no encontrada.')

if __name__ == '__main__':
    serve(Availability, 8106)
