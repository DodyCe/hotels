"""Inventario propio y ocupación por noche. Asignación y liberación idempotentes."""
import datetime as dt
import json
import re
import postgres
import validation
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit
from common import APIError, Handler, ROOMS, admin_for, connect, internal_request, serve, validate_dates

seed = json.loads((Path(__file__).resolve().parents[1] / 'seed' / 'inventory.json').read_text(encoding='utf-8'))
with connect('availability') as db:
    if postgres.database_url('availability'):
        postgres.initialize('availability', db)
        db.execute('SELECT 1 FROM room_numbers LIMIT 1')
    else:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS inventory (room_id TEXT PRIMARY KEY, total INTEGER NOT NULL CHECK(total>=1));
        CREATE TABLE IF NOT EXISTS allocations (reservation_id TEXT PRIMARY KEY, room_id TEXT NOT NULL DEFAULT '', checkin TEXT NOT NULL DEFAULT '', checkout TEXT NOT NULL DEFAULT '', status TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS allocation_dates ON allocations(room_id,status,checkin,checkout);
        CREATE TABLE IF NOT EXISTS room_numbers (
            hotel_id TEXT NOT NULL,
            number TEXT NOT NULL,
            room_id TEXT NOT NULL REFERENCES inventory(room_id) ON DELETE CASCADE,
            PRIMARY KEY(hotel_id,number)
        );
        CREATE INDEX IF NOT EXISTS room_numbers_by_type ON room_numbers(room_id);
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


def physical_numbers(values, total):
    if not isinstance(values, list) or len(values) > total:
        raise APIError(400, 'Los números físicos deben ser una lista con un máximo de un número por unidad.')
    numbers = []
    for value in values:
        number = value.strip() if isinstance(value, str) else ''
        if len(number) > 12 or not re.fullmatch(r'[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*', number):
            raise APIError(400, 'Cada número físico debe tener hasta 12 caracteres: letras, números o guiones, como 101-A.')
        numbers.append(number.upper())
    if len(set(numbers)) != len(numbers):
        raise APIError(400, 'Hay números físicos repetidos en la lista.')
    return numbers


def inventory_numbers(db, room):
    rows = db.execute('SELECT number FROM room_numbers WHERE room_id=? ORDER BY number', (room,)).fetchall()
    return [row['number'] for row in rows]


def replace_numbers(db, hotel, room, numbers):
    db.execute('DELETE FROM room_numbers WHERE room_id=?', (room,))
    if not numbers:
        return
    values = ','.join(['(?,?,?)'] * len(numbers))
    params = tuple(value for number in numbers for value in (hotel,number,room))
    inserted = db.execute(
        f'INSERT INTO room_numbers(hotel_id,number,room_id) VALUES {values} '
        'ON CONFLICT(hotel_id,number) DO NOTHING RETURNING number',
        params,
    ).fetchall()
    if len(inserted) != len(numbers):
        saved = {row['number'] for row in inserted}
        conflict = next(number for number in numbers if number not in saved)
        raise APIError(409, f'El número {conflict} ya pertenece a otro tipo de habitación de este hotel.')

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
        if self.command in ('GET', 'PUT') and url.path.startswith('/inventory/'):
            admin_for(self)
            room = url.path.removeprefix('/inventory/')
            if self.command == 'GET':
                with connect('availability') as db:
                    row = db.execute(
                        'SELECT i.total,n.number FROM inventory i LEFT JOIN room_numbers n ON n.room_id=i.room_id WHERE i.room_id=? ORDER BY n.number',
                        (room,),
                    ).fetchall()
                    if not row:
                        raise APIError(404,'Habitación no registrada en inventario.')
                    numbers = [item['number'] for item in row if item['number'] is not None]
                return self.respond(200,{'inventory':{'roomId':room,'total':row[0]['total'],'roomNumbers':numbers}})
            data = self.body()
            total = validation.integer(data.get('total'),'Las unidades',1,1000)
            numbers = physical_numbers(data['roomNumbers'], total) if 'roomNumbers' in data else None
            hotel = None
            if numbers is not None:
                hotel = internal_request(ROOMS, '/rooms/'+quote(room,safe='')+'?includeInactive=true',
                                         cookie=self.headers.get('Cookie',''))['room']['hotelId']
            with connect('availability') as db:
                if not postgres.database_url('availability'):
                    db.execute('BEGIN IMMEDIATE')
                elif hotel is not None:
                    db.execute('SELECT pg_advisory_xact_lock(hashtextextended(?,0))', ('room-numbers:'+hotel,))
                lock_room(db,room)
                if not db.execute('SELECT room_id FROM inventory WHERE room_id=?',(room,)).fetchone():
                    raise APIError(404,'Habitación no registrada en inventario.')
                peak = future_peak(db,room)
                if total < peak:
                    raise APIError(409,'Hay '+str(peak)+' unidades comprometidas; no puedes reducir el inventario por debajo de las reservas vigentes.')
                if numbers is None:
                    numbers = inventory_numbers(db,room)
                    if total < len(numbers):
                        raise APIError(409,'Retira los números físicos que correspondan antes de reducir las unidades.')
                else:
                    replace_numbers(db,hotel,room,numbers)
                db.execute('UPDATE inventory SET total=? WHERE room_id=?',(total,room))
            return self.respond(200,{'inventory':{'roomId':room,'total':total,'roomNumbers':sorted(numbers)}})
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
