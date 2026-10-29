"""Catálogo de hoteles. No contiene habitaciones, precios ni inventario."""
import json
import postgres
import uuid
import validation
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from common import APIError, Handler, admin_for, connect, serve

seed = json.loads((Path(__file__).resolve().parents[1] / 'seed' / 'hotels.json').read_text(encoding='utf-8'))
with connect('catalog') as db:
    if postgres.database_url('catalog'):
        postgres.initialize('catalog', db)
        db.execute('SELECT active FROM hotels LIMIT 1')
    else:
        db.execute('CREATE TABLE IF NOT EXISTS hotels (id TEXT PRIMARY KEY, document TEXT NOT NULL)')
        db.executemany('INSERT OR IGNORE INTO hotels(id,document) VALUES (?,?)', [(h['id'], json.dumps(h, ensure_ascii=False)) for h in seed])
        if 'active' not in {r['name'] for r in db.execute('PRAGMA table_info(hotels)')}:
            db.execute('ALTER TABLE hotels ADD COLUMN active INTEGER NOT NULL DEFAULT 1')


def public_hotel(row):
    return {**json.loads(row['document']), 'active':bool(row['active'])}


def hotel_document(data, existing=None):
    allowed = {'name','area','address','description','tags','amenities','image','photographer','photoPage','source','badge','active'}
    if set(data) - allowed:
        raise APIError(400, 'El hotel contiene campos no editables.')
    value = {**(existing or {}), **data}
    result = {'city':'Montería'}
    for key, maximum in (('name',120),('area',100),('address',180),('description',1000)):
        result[key] = validation.text(value.get(key), key, maximum, 2)
    result['badge'] = validation.text(value.get('badge',result['area']), 'La etiqueta',60)
    tags = value.get('tags',[])
    if not isinstance(tags,list) or any(t not in ('wifi','restaurant','work') for t in tags):
        raise APIError(400, 'Los servicios del hotel no son válidos.')
    result['tags'] = list(dict.fromkeys(tags))
    amenities = value.get('amenities',[])
    if not isinstance(amenities,list) or len(amenities)>12:
        raise APIError(400, 'Indica hasta doce comodidades.')
    result['amenities'] = [validation.text(a,'La comodidad',60) for a in amenities]
    result['image'] = validation.url(value.get('image',seed[0]['image']),'La fotografía',{'images.unsplash.com'})
    result['photographer'] = validation.text(value.get('photographer',seed[0]['photographer']),'El autor',100)
    result['photoPage'] = validation.url(value.get('photoPage',seed[0]['photoPage']),'El crédito',{'unsplash.com','www.unsplash.com'})
    result['source'] = validation.url(value.get('source'),'La web del hotel')
    return result, validation.active(value.get('active',True))

class Catalog(Handler):
    service_name = 'catalogo-hoteles'
    database_name = 'catalog'
    def route(self):
        url = urlsplit(self.path)
        path = url.path
        if path != '/hotels' and not path.startswith('/hotels/'):
            raise APIError(404, 'Hotel no encontrado.')
        identifier = path.removeprefix('/hotels/') if path != '/hotels' else None
        include_inactive = parse_qs(url.query).get('includeInactive') == ['true']
        if include_inactive or self.command != 'GET':
            admin_for(self)
        if self.command == 'POST' and identifier is None:
            document, enabled = hotel_document(self.body())
            identifier = 'hotel-' + uuid.uuid4().hex[:16]
            document['id'] = identifier
            with connect('catalog') as db:
                if postgres.database_url('catalog'):
                    position = db.execute('SELECT COALESCE(MAX(sort_order),-1)+1 AS position FROM hotels').fetchone()['position']
                    db.execute('INSERT INTO hotels(id,document,sort_order,active) VALUES (?,?,?,?)',(identifier,json.dumps(document,ensure_ascii=False),position,enabled))
                else:
                    db.execute('INSERT INTO hotels(id,document,active) VALUES (?,?,?)',(identifier,json.dumps(document,ensure_ascii=False),enabled))
            return self.respond(201, {'hotel':{**document,'active':bool(enabled)}})
        if self.command in ('PATCH','DELETE') and identifier:
            data = self.body() if self.command == 'PATCH' else {'active':False}
            with connect('catalog') as db:
                row = db.execute('SELECT document,active FROM hotels WHERE id=?',(identifier,)).fetchone()
                if not row:
                    raise APIError(404,'Hotel no encontrado.')
                document, enabled = hotel_document(data,public_hotel(row))
                document['id'] = identifier
                db.execute('UPDATE hotels SET document=?,active=? WHERE id=?',(json.dumps(document,ensure_ascii=False),enabled,identifier))
            return self.respond(200, {'hotel':{**document,'active':bool(enabled)}})
        if self.command != 'GET':
            raise APIError(405, 'Método no permitido para hoteles.')
        with connect('catalog') as db:
            if path == '/hotels':
                ordering = 'sort_order,id' if postgres.database_url('catalog') else 'rowid'
                rows = db.execute('SELECT document,active FROM hotels WHERE (active=1 OR ?=1) ORDER BY ' + ordering,(int(include_inactive),)).fetchall()
                return self.respond(200, {'hotels': [public_hotel(r) for r in rows]})
            if path.startswith('/hotels/'):
                row = db.execute('SELECT document,active FROM hotels WHERE id=? AND (active=1 OR ?=1)', (identifier,int(include_inactive))).fetchone()
                if row:
                    return self.respond(200, {'hotel': public_hotel(row)})
        raise APIError(404, 'Hotel no encontrado.')

if __name__ == '__main__':
    serve(Catalog, 8104)
