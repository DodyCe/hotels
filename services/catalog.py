"""Catálogo de hoteles. No contiene habitaciones, precios ni inventario."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from common import APIError, Handler, connect, serve

seed = json.loads((Path(__file__).resolve().parents[1] / 'seed' / 'hotels.json').read_text(encoding='utf-8'))
with connect('catalog') as db:
    db.execute('CREATE TABLE IF NOT EXISTS hotels (id TEXT PRIMARY KEY, document TEXT NOT NULL)')
    db.executemany('INSERT OR IGNORE INTO hotels VALUES (?,?)', [(h['id'], json.dumps(h, ensure_ascii=False)) for h in seed])

class Catalog(Handler):
    service_name = 'catalogo-hoteles'
    def route(self):
        path = urlsplit(self.path).path
        if self.command != 'GET':
            raise APIError(405, 'El catálogo de referencia se consulta con GET.')
        with connect('catalog') as db:
            if path == '/hotels':
                rows = db.execute('SELECT document FROM hotels ORDER BY rowid').fetchall()
                return self.respond(200, {'hotels': [json.loads(r['document']) for r in rows]})
            if path.startswith('/hotels/'):
                row = db.execute('SELECT document FROM hotels WHERE id=?', (path.removeprefix('/hotels/'),)).fetchone()
                if row:
                    return self.respond(200, {'hotel': json.loads(row['document'])})
        raise APIError(404, 'Hotel no encontrado.')

if __name__ == '__main__':
    serve(Catalog, 8104)
