"""Habitaciones: tipos, pertenencia a hotel, capacidad y tarifa de referencia."""
import json
import postgres
import logging
import threading
import time
import uuid
import validation
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from common import APIError, AVAILABILITY, CATALOG, Handler, admin_for, connect, internal_request, serve

seed = json.loads((Path(__file__).resolve().parents[1] / 'seed' / 'rooms.json').read_text(encoding='utf-8'))
with connect('rooms') as db:
    if postgres.database_url('rooms'):
        postgres.initialize('rooms', db)
        db.execute('SELECT active,inventory_ready,initial_units FROM rooms LIMIT 1')
    else:
        db.execute('CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, hotelId TEXT NOT NULL, name TEXT NOT NULL, capacity INTEGER NOT NULL, price INTEGER NOT NULL)')
        db.executemany('INSERT OR IGNORE INTO rooms(id,hotelId,name,capacity,price) VALUES (:id,:hotelId,:name,:capacity,:price)', seed)
        columns = {r['name'] for r in db.execute('PRAGMA table_info(rooms)')}
        for column, definition in (('active','INTEGER NOT NULL DEFAULT 1'),('inventory_ready','INTEGER NOT NULL DEFAULT 1'),('initial_units','INTEGER NOT NULL DEFAULT 1')):
            if column not in columns:
                db.execute('ALTER TABLE rooms ADD COLUMN ' + column + ' ' + definition)


def public_room(row):
    return {key:(bool(row[key]) if key in ('active','inventory_ready') else row[key]) for key in ('id','hotelId','name','capacity','price','active','inventory_ready')}


def synchronize_inventory(identifier):
    with connect('rooms') as db:
        row = db.execute('SELECT id,initial_units,inventory_ready FROM rooms WHERE id=?',(identifier,)).fetchone()
    if not row or row['inventory_ready']:
        return
    internal_request(AVAILABILITY,'/internal/inventory',{'roomId':row['id'],'total':row['initial_units']})
    with connect('rooms') as db:
        db.execute('UPDATE rooms SET inventory_ready=1 WHERE id=?',(identifier,))


def inventory_worker():
    while True:
        try:
            with connect('rooms') as db:
                pending = db.execute('SELECT id FROM rooms WHERE inventory_ready=0').fetchall()
            for row in pending:
                try:
                    synchronize_inventory(row['id'])
                except APIError:
                    logging.warning('Alta de inventario pendiente para %s',row['id'])
        except Exception:
            logging.exception('Error recuperando altas de habitaciones')
        time.sleep(3)

class Rooms(Handler):
    service_name = 'habitaciones'
    database_name = 'rooms'
    def route(self):
        url = urlsplit(self.path)
        if url.path != '/rooms' and not url.path.startswith('/rooms/'):
            raise APIError(404,'Habitación no encontrada.')
        identifier = url.path.removeprefix('/rooms/') if url.path != '/rooms' else None
        include_inactive = parse_qs(url.query).get('includeInactive') == ['true']
        if include_inactive or self.command != 'GET':
            admin_for(self)
        if self.command == 'POST' and identifier is None:
            data = self.body()
            if set(data)-{'hotelId','name','capacity','price','total'}:
                raise APIError(400,'La habitación contiene campos no editables.')
            hotel_id = validation.text(data.get('hotelId'),'El hotel',100)
            internal_request(CATALOG,'/hotels/'+hotel_id)
            name = validation.text(data.get('name'),'El nombre',120,2)
            capacity = validation.integer(data.get('capacity'),'La capacidad',1,20)
            price = validation.integer(data.get('price'),'La tarifa',1,100000000)
            total = validation.integer(data.get('total'),'Las unidades',1,1000)
            identifier = 'room-' + uuid.uuid4().hex[:16]
            with connect('rooms') as db:
                if postgres.database_url('rooms'):
                    position = db.execute('SELECT COALESCE(MAX(sort_order),-1)+1 AS position FROM rooms').fetchone()['position']
                    db.execute('INSERT INTO rooms(id,"hotelId",name,capacity,price,sort_order,inventory_ready,initial_units) VALUES (?,?,?,?,?,?,0,?)',(identifier,hotel_id,name,capacity,price,position,total))
                else:
                    db.execute('INSERT INTO rooms(id,hotelId,name,capacity,price,inventory_ready,initial_units) VALUES (?,?,?,?,?,0,?)',(identifier,hotel_id,name,capacity,price,total))
            try:
                synchronize_inventory(identifier)
            except APIError:
                pass
            with connect('rooms') as db:
                row = db.execute('SELECT * FROM rooms WHERE id=?',(identifier,)).fetchone()
            return self.respond(201 if row['inventory_ready'] else 202,{'room':public_room(row)})
        if self.command in ('PATCH','DELETE') and identifier:
            data = self.body() if self.command == 'PATCH' else {'active':False}
            if set(data)-{'name','capacity','price','active'}:
                raise APIError(400,'El hotel y el inventario se gestionan por separado; solo se editan nombre, capacidad, tarifa y estado.')
            with connect('rooms') as db:
                row = db.execute('SELECT * FROM rooms WHERE id=?',(identifier,)).fetchone()
                if not row:
                    raise APIError(404,'Habitación no encontrada.')
                name = validation.text(data.get('name',row['name']),'El nombre',120,2)
                capacity = validation.integer(data.get('capacity',row['capacity']),'La capacidad',1,20)
                price = validation.integer(data.get('price',row['price']),'La tarifa',1,100000000)
                enabled = validation.active(data.get('active',bool(row['active'])))
                db.execute('UPDATE rooms SET name=?,capacity=?,price=?,active=? WHERE id=?',(name,capacity,price,enabled,identifier))
                row = db.execute('SELECT * FROM rooms WHERE id=?',(identifier,)).fetchone()
            return self.respond(200,{'room':public_room(row)})
        if self.command != 'GET':
            raise APIError(405,'Método no permitido para habitaciones.')
        with connect('rooms') as db:
            if url.path == '/rooms':
                query = parse_qs(url.query)
                hotel_id = query.get('hotelId', [''])[0]
                try:
                    guests = int(query.get('guests', ['1'])[0])
                    if not 1 <= guests <= 20:
                        raise ValueError()
                except ValueError:
                    raise APIError(400, 'Número de huéspedes inválido.') from None
                ordering = 'sort_order,id' if postgres.database_url('rooms') else 'rowid'
                rows = db.execute('SELECT * FROM rooms WHERE (CAST(? AS TEXT)=\'\' OR "hotelId"=?) AND capacity>=? AND ((active=1 AND inventory_ready=1) OR ?=1) ORDER BY ' + ordering, (hotel_id, hotel_id, guests,int(include_inactive))).fetchall()
                return self.respond(200, {'rooms': [public_room(r) for r in rows]})
            if url.path.startswith('/rooms/'):
                row = db.execute('SELECT * FROM rooms WHERE id=? AND ((active=1 AND inventory_ready=1) OR ?=1)', (identifier,int(include_inactive))).fetchone()
                if row:
                    return self.respond(200, {'room': public_room(row)})
        raise APIError(404, 'Habitación no encontrada.')

if __name__ == '__main__':
    threading.Thread(target=inventory_worker,daemon=True).start()
    serve(Rooms, 8105)
