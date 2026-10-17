"""Reservas coordina APIs independientes y persiste estados para reintentar caídas."""
import logging
import threading
import time
import uuid
from urllib.parse import urlsplit
from common import (APIError, AVAILABILITY, CATALOG, ROOMS, Handler, connect,
                    enqueue, init_outbox, internal_request, serve, start_outbox,
                    user_for, validate_dates)

with connect('reservations') as db:
    db.execute('''CREATE TABLE IF NOT EXISTS reservations (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, hotel_id TEXT NOT NULL,
        checkin TEXT NOT NULL, checkout TEXT NOT NULL, guests INTEGER NOT NULL,
        total INTEGER NOT NULL, status TEXT NOT NULL, created REAL NOT NULL)''')
    columns = {r['name'] for r in db.execute('PRAGMA table_info(reservations)')}
    for column, definition in [('room_id',"TEXT NOT NULL DEFAULT ''"),
                               ('hotel_name',"TEXT NOT NULL DEFAULT ''"),
                               ('room_name',"TEXT NOT NULL DEFAULT ''"),
                               ('inventory_synced','INTEGER NOT NULL DEFAULT 0')]:
        if column not in columns:
            db.execute(f'ALTER TABLE reservations ADD COLUMN {column} {definition}')
    init_outbox(db)

transition_lock = threading.RLock()

def reservation(rid):
    with connect('reservations') as db:
        return db.execute('SELECT * FROM reservations WHERE id=?', (rid,)).fetchone()

def public_reservation(row):
    result = dict(row)
    result['hotel'], result['room'] = row['hotel_name'], row['room_name']
    result.pop('inventory_synced', None)
    return result

def finish(rid):
    """Inventario reconoce rid como clave idempotente; no se leen bases ajenas."""
    with transition_lock:
        row = reservation(rid)
        if not row:
            return
        if not row['room_id']:
            # Migra los cupos de la versión anterior al tipo principal del hotel.
            hotel = internal_request(CATALOG, '/hotels/' + row['hotel_id'])['hotel']
            room = internal_request(ROOMS, '/rooms/' + row['hotel_id'] + '-principal')['room']
            with connect('reservations') as db:
                db.execute('UPDATE reservations SET room_id=?,hotel_name=?,room_name=? WHERE id=?', (room['id'],hotel['name'],room['name'],rid))
            row = reservation(rid)
        pending = row['status'] == 'Pendiente'
        migrating = row['status'] == 'Confirmada' and not row['inventory_synced']
        if pending or migrating:
            try:
                internal_request(AVAILABILITY, '/internal/allocate', {
                    'reservationId':rid, 'roomId':row['room_id'],
                    'checkin':row['checkin'], 'checkout':row['checkout']})
            except APIError as error:
                if error.status in (400,404,409) and pending:
                    with connect('reservations') as db:
                        db.execute("UPDATE reservations SET status='Rechazada',inventory_synced=1 WHERE id=?", (rid,))
                    return
                raise
            with connect('reservations') as db:
                db.execute("UPDATE reservations SET status='Confirmada',inventory_synced=1 WHERE id=?", (rid,))
                if pending:
                    payload = public_reservation(db.execute('SELECT * FROM reservations WHERE id=?',(rid,)).fetchone())
                    enqueue(db, {'id':'confirmed:'+rid,'userId':row['user_id'],'kind':'reservation.confirmed','payload':payload})
        elif row['status'] == 'Cancelando':
            internal_request(AVAILABILITY, '/internal/release', {'reservationId':rid})
            with connect('reservations') as db:
                db.execute("UPDATE reservations SET status='Cancelada',inventory_synced=1 WHERE id=?", (rid,))
                payload = public_reservation(db.execute('SELECT * FROM reservations WHERE id=?',(rid,)).fetchone())
                enqueue(db, {'id':'cancelled:'+rid,'userId':row['user_id'],'kind':'reservation.cancelled','payload':payload})
        elif not row['inventory_synced']:
            # Las cancelaciones antiguas no ocupan cupos ni reenvían avisos.
            with connect('reservations') as db:
                db.execute('UPDATE reservations SET inventory_synced=1 WHERE id=?', (rid,))

def reconcile_once():
    with connect('reservations') as db:
        rows = db.execute("SELECT id FROM reservations WHERE inventory_synced=0 OR room_id='' OR status IN ('Pendiente','Cancelando') ORDER BY created").fetchall()
    for row in rows:
        try:
            finish(row['id'])
        except APIError:
            pass
    with connect('reservations') as db:
        return db.execute("SELECT count(*) FROM reservations WHERE inventory_synced=0 OR room_id='' OR status IN ('Pendiente','Cancelando')").fetchone()[0]

def reconcile_worker():
    while True:
        try:
            reconcile_once()
        except Exception:
            logging.exception('Error reconciliando reservas e inventario')
        time.sleep(2)

class Reservations(Handler):
    service_name = 'reservas'
    def health(self):
        with connect('reservations') as db:
            legacy = db.execute("SELECT count(*) FROM reservations WHERE room_id='' OR (status='Confirmada' AND inventory_synced=0)").fetchone()[0]
        return self.respond(503 if legacy else 200, {'status':'migrating' if legacy else 'ok','service':self.service_name})
    def route(self):
        path = urlsplit(self.path).path
        if self.command == 'POST' and path == '/internal/reconcile':
            self.body()
            return self.respond(200, {'pending':reconcile_once()})
        user = user_for(self)
        if self.command == 'GET' and path == '/reservations':
            with connect('reservations') as db:
                rows = db.execute('SELECT * FROM reservations WHERE user_id=? ORDER BY created DESC', (user['id'],)).fetchall()
            return self.respond(200, {'reservations':[public_reservation(r) for r in rows]})
        if self.command == 'POST' and path == '/reservations':
            data = self.body()
            room_id = data.get('roomId')
            if not isinstance(room_id,str) or not 1 <= len(room_id) <= 120:
                raise APIError(400,'Selecciona una habitación válida.')
            room = internal_request(ROOMS, '/rooms/' + room_id)['room']
            if data.get('hotelId') is not None and data['hotelId'] != room['hotelId']:
                raise APIError(400,'La habitación no pertenece al hotel indicado.')
            hotel = internal_request(CATALOG,'/hotels/'+room['hotelId'])['hotel']
            guests = data.get('guests')
            if type(guests) is not int or not 1 <= guests <= room['capacity']:
                raise APIError(400,'Cantidad de huéspedes inválida para la habitación.')
            start,end = validate_dates(data.get('checkin'),data.get('checkout'))
            rid = 'HT-' + uuid.uuid4().hex[:10].upper()
            with connect('reservations') as db:
                db.execute('''INSERT INTO reservations
                    (id,user_id,hotel_id,checkin,checkout,guests,total,status,created,room_id,hotel_name,room_name,inventory_synced)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)''',
                    (rid,user['id'],hotel['id'],start.isoformat(),end.isoformat(),guests,
                     room['price']*(end-start).days,'Pendiente',time.time(),room_id,hotel['name'],room['name']))
            try:
                finish(rid)
            except APIError:
                pass
            row = reservation(rid)
            if row['status'] == 'Rechazada':
                raise APIError(409,'La habitación ya no tiene cupos para esas fechas.')
            return self.respond(201 if row['status']=='Confirmada' else 202, {'reservation':public_reservation(row)})
        if self.command == 'POST' and path.startswith('/reservations/') and path.endswith('/cancel'):
            rid = path.split('/')[2]
            self.body()
            with transition_lock:
                with connect('reservations') as db:
                    row = db.execute('SELECT * FROM reservations WHERE id=? AND user_id=?',(rid,user['id'])).fetchone()
                    if not row:
                        raise APIError(404,'Reserva no encontrada.')
                    if row['status'] in ('Cancelada','Rechazada'):
                        return self.respond(200,{'ok':True,'status':row['status']})
                    db.execute("UPDATE reservations SET status='Cancelando' WHERE id=?",(rid,))
                try:
                    finish(rid)
                except APIError:
                    pass
            status = reservation(rid)['status']
            return self.respond(200 if status=='Cancelada' else 202,{'ok':True,'status':status})
        raise APIError(404,'Ruta no encontrada.')

if __name__ == '__main__':
    start_outbox('reservations')
    threading.Thread(target=reconcile_worker,daemon=True).start()
    serve(Reservations,8103)
