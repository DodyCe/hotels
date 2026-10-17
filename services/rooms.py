"""Habitaciones: tipos, pertenencia a hotel, capacidad y tarifa de práctica."""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from common import APIError, Handler, connect, serve

seed = json.loads((Path(__file__).resolve().parents[1] / 'seed' / 'rooms.json').read_text(encoding='utf-8'))
with connect('rooms') as db:
    db.execute('CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, hotelId TEXT NOT NULL, name TEXT NOT NULL, capacity INTEGER NOT NULL, price INTEGER NOT NULL)')
    db.executemany('INSERT OR IGNORE INTO rooms VALUES (:id,:hotelId,:name,:capacity,:price)', seed)

class Rooms(Handler):
    service_name = 'habitaciones'
    def route(self):
        url = urlsplit(self.path)
        if self.command != 'GET':
            raise APIError(405, 'Las habitaciones se consultan con GET.')
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
                rows = db.execute('SELECT * FROM rooms WHERE (?=\'\' OR hotelId=?) AND capacity>=? ORDER BY rowid', (hotel_id, hotel_id, guests)).fetchall()
                return self.respond(200, {'rooms': [dict(r) for r in rows]})
            if url.path.startswith('/rooms/'):
                row = db.execute('SELECT * FROM rooms WHERE id=?', (url.path.removeprefix('/rooms/'),)).fetchone()
                if row:
                    return self.respond(200, {'room': dict(row)})
        raise APIError(404, 'Habitación no encontrada.')

if __name__ == '__main__':
    serve(Rooms, 8105)
