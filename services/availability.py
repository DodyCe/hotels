"""Inventario propio y ocupación por noche. Asignación y liberación idempotentes."""
import datetime as dt
import json
import postgres
import validation
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from common import APIError, Handler, admin_for, connect, serve, validate_dates

seed = json.loads((Path(__file__).resolve().parents[1] / 'seed' / 'inventory.json').read_text(encoding='utf-8'))
with connect('availability') as db:
    if postgres.database_url('availability'):
        postgres.initialize('availability', db)
    else:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS inventory (room_id TEXT PRIMARY KEY, total INTEGER NOT NULL CHECK(total>=1));
        CREATE TABLE IF NOT EXISTS allocations (reservation_id TEXT PRIMARY KEY, room_id TEXT NOT NULL DEFAULT '', checkin TEXT NOT NULL DEFAULT '', checkout TEXT NOT NULL DEFAULT '', status TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS allocation_dates ON allocations(room_id,status,checkin,checkout);
        ''')
        db.executemany('INSERT OR IGNORE INTO inventory VALUES (:roomId,:total)', seed)

def begin_allocation(db, rid):
    if postgres.database_url('availability'):
        db.execute('SELECT pg_advisory_xact_lock(hashtextextended(?,0))', ('allocation:'+rid,))
    else:
        db.execute('BEGIN IMMEDIATE')

def lock_room(db, room_id):
    if postgres.database_url('availability'):
        db.execute('SELECT total FROM inventory WHERE room_id=? FOR UPDATE', (room_id,)).fetchone()

def available_units(db, room_id, start, end, total=None):
    if total is None:
        row = db.execute('SELECT total FROM inventory WHERE room_id=?', (room_id,)).fetchone()
        if not row:
            raise APIError(404, 'Habitación no registrada en el inventario.')
        total = row['total']
    # Una consulta por habitación, en lugar de un viaje de red por cada noche.
    allocations = db.execute("SELECT checkin,checkout FROM allocations WHERE room_id=? AND status='Asignada' AND checkin<? AND checkout>?",
                             (room_id,end.isoformat(),start.isoformat())).fetchall()
    result = total
    day = start
    while day < end:
        date = day.isoformat()
        occupied = sum(row['checkin'] <= date < row['checkout'] for row in allocations)
        result = min(result, total-occupied)
        day += dt.timedelta(days=1)
    return max(0, result)

def validate_id(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 160:
        raise APIError(400, 'Identificador de reserva inválido.')
    return value


def future_peak(db, room):
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).date().isoformat()
    rows = db.execute("SELECT checkin,checkout FROM allocations WHERE room_id=? AND status='Asignada' AND checkout>?",(room,today)).fetchall()
    changes = {}
    for row in rows:
        start = max(today,row['checkin'])
        changes[start] = changes.get(start,0)+1
        changes[row['checkout']] = changes.get(row['checkout'],0)-1
    occupied = peak = 0
    for day in sorted(changes):
        occupied += changes[day]
        peak = max(peak,occupied)
    return peak

class Availability(Handler):
    service_name = 'disponibilidad-inventario'
    database_name = 'availability'
    def route(self):
        url = urlsplit(self.path)
        if self.command == 'POST' and url.path == '/internal/inventory':
            data = self.body()
            room = validation.text(data.get('roomId'),'La habitación',120)
            total = validation.integer(data.get('total'),'Las unidades',1,1000)
            with connect('availability') as db:
                if postgres.database_url('availability'):
                    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(?,0))",('inventory:'+room,))
                    position = db.execute('SELECT COALESCE(MAX(sort_order),-1)+1 AS position FROM inventory').fetchone()['position']
                    db.execute('INSERT INTO inventory(room_id,total,sort_order) VALUES (?,?,?) ON CONFLICT(room_id) DO NOTHING',(room,total,position))
                else:
                    db.execute('BEGIN IMMEDIATE')
                    db.execute('INSERT OR IGNORE INTO inventory(room_id,total) VALUES (?,?)',(room,total))
                row = db.execute('SELECT total FROM inventory WHERE room_id=?',(room,)).fetchone()
            return self.respond(200,{'inventory':{'roomId':room,'total':row['total']}})
        if self.command == 'PUT' and url.path.startswith('/inventory/'):
            admin_for(self)
            room = url.path.removeprefix('/inventory/')
            total = validation.integer(self.body().get('total'),'Las unidades',1,1000)
            with connect('availability') as db:
                if not postgres.database_url('availability'):
                    db.execute('BEGIN IMMEDIATE')
                lock_room(db,room)
                if not db.execute('SELECT room_id FROM inventory WHERE room_id=?',(room,)).fetchone():
                    raise APIError(404,'Habitación no registrada en inventario.')
                peak = future_peak(db,room)
                if total < peak:
                    raise APIError(409,'Hay '+str(peak)+' unidades comprometidas; no puedes reducir el inventario por debajo de las reservas vigentes.')
                db.execute('UPDATE inventory SET total=? WHERE room_id=?',(total,room))
            return self.respond(200,{'inventory':{'roomId':room,'total':total}})
        if self.command == 'GET' and url.path == '/inventory':
            with connect('availability') as db:
                ordering = 'sort_order,room_id' if postgres.database_url('availability') else 'rowid'
                rows = db.execute('SELECT room_id AS "roomId",total FROM inventory ORDER BY ' + ordering).fetchall()
            return self.respond(200, {'inventory': [dict(r) for r in rows]})
        if self.command == 'GET' and url.path == '/availability':
            query = parse_qs(url.query)
            a, b = validate_dates(query.get('checkin', [''])[0], query.get('checkout', [''])[0])
            with connect('availability') as db:
                ordering = 'sort_order,room_id' if postgres.database_url('availability') else 'rowid'
                rows = db.execute('SELECT room_id,total FROM inventory ORDER BY ' + ordering).fetchall()
                result = [{'roomId':r['room_id'],'total':r['total'],'available':available_units(db,r['room_id'],a,b,r['total'])} for r in rows]
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
                begin_allocation(db, rid)
                existing = db.execute('SELECT * FROM allocations WHERE reservation_id=?', (rid,)).fetchone()
                if existing:
                    if existing['status'] == 'Liberada':
                        raise APIError(409, 'La reserva ya fue liberada y no puede reactivarse.')
                    if (existing['room_id'],existing['checkin'],existing['checkout']) != (room,a.isoformat(),b.isoformat()):
                        raise APIError(409, 'El identificador ya corresponde a otra asignación.')
                    return self.respond(200, {'allocated': True, 'duplicate': True})
                lock_room(db, room)
                if available_units(db,room,a,b) < 1:
                    raise APIError(409, 'La habitación no tiene cupos para esas fechas.')
                db.execute('INSERT INTO allocations VALUES (?,?,?,?,?)', (rid,room,a.isoformat(),b.isoformat(),'Asignada'))
            return self.respond(201, {'allocated': True})
        if self.command == 'POST' and url.path == '/internal/release':
            rid = validate_id(self.body().get('reservationId'))
            with connect('availability') as db:
                begin_allocation(db, rid)
                existing = db.execute('SELECT room_id FROM allocations WHERE reservation_id=?', (rid,)).fetchone()
                if existing and existing['room_id']:
                    lock_room(db, existing['room_id'])
                # Una liberación desconocida deja una marca que impide asignaciones tardías.
                db.execute("INSERT INTO allocations(reservation_id,status) VALUES (?,'Liberada') ON CONFLICT(reservation_id) DO UPDATE SET status='Liberada'", (rid,))
            return self.respond(200, {'released': True})
        raise APIError(404, 'Ruta no encontrada.')

if __name__ == '__main__':
    serve(Availability, 8106)
