import sqlite3
import sys
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.migrate_supabase import inspect_rows, snapshot_sources


def target():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE users(id TEXT PRIMARY KEY,name TEXT,email TEXT UNIQUE,salt TEXT,password_hash TEXT,created REAL,role TEXT DEFAULT 'guest',active INTEGER DEFAULT 1);
        CREATE TABLE guests(id TEXT PRIMARY KEY,user_id TEXT,name TEXT,email TEXT,phone TEXT,created REAL,active INTEGER DEFAULT 1);
        CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id TEXT,expires REAL);
        CREATE TABLE outbox(id TEXT PRIMARY KEY,body TEXT,attempts INTEGER,next_try REAL,delivered INTEGER);
    ''')
    return db


def user(identifier='fixture'):
    return dict(id=identifier,name='Prueba',email=identifier+'@example.test',salt='salt',password_hash='hash',created=1.25)


class Migration(unittest.TestCase):
    def test_guest_retry_does_not_reactivate_archived_profile(self):
        with closing(target()) as db:
            source={'users':[user()], 'guests':[dict(id='g',user_id='fixture',name='Prueba',email='fixture@example.test',phone='',created=1.25,active=1)]}
            with db:inspect_rows('auth',source,db,apply=True)
            with db:db.execute('UPDATE guests SET active=0')
            with db:self.assertEqual(inspect_rows('auth',source,db,apply=True)['guests']['copiados'],0)
            self.assertEqual(db.execute('SELECT active FROM guests').fetchone()[0],0)
    def test_reservation_retry_does_not_reopen_cancelled_remote_state(self):
        source = {'reservations':[dict(id='r',user_id='u',hotel_id='h',checkin='2030-01-01',checkout='2030-01-02',guests=2,total=100,status='Pendiente',created=1.25,room_id='room',hotel_name='Hotel',room_name='Doble',inventory_synced=0)]}
        with closing(sqlite3.connect(':memory:')) as db:
            db.row_factory=sqlite3.Row
            db.execute('CREATE TABLE reservations(id TEXT PRIMARY KEY,user_id TEXT,hotel_id TEXT,checkin TEXT,checkout TEXT,guests INTEGER,total INTEGER,status TEXT,created REAL,room_id TEXT,hotel_name TEXT,room_name TEXT,inventory_synced INTEGER)')
            db.execute('CREATE TABLE outbox(id TEXT PRIMARY KEY,body TEXT)')
            with db: inspect_rows('reservations',source,db,apply=True)
            with db: db.execute("UPDATE reservations SET status='Cancelada',inventory_synced=1")
            with db: self.assertEqual(inspect_rows('reservations',source,db,apply=True)['reservations']['copiados'],0)
            row=dict(db.execute('SELECT * FROM reservations').fetchone())
            self.assertEqual((row['status'],row['inventory_synced'],row['total']),('Cancelada',1,100))

    def test_inventory_retry_preserves_release_and_unknown_release_marker(self):
        source={'allocations':[dict(reservation_id='r',room_id='room',checkin='2030-01-01',checkout='2030-01-02',status='Asignada'),
                               dict(reservation_id='unknown',room_id='',checkin='',checkout='',status='Liberada')]}
        with closing(sqlite3.connect(':memory:')) as db:
            db.row_factory=sqlite3.Row
            db.execute("CREATE TABLE allocations(reservation_id TEXT PRIMARY KEY,room_id TEXT,checkin TEXT,checkout TEXT,status TEXT)")
            db.execute('CREATE TABLE inventory(room_id TEXT PRIMARY KEY,total INTEGER,sort_order INTEGER)')
            with db: inspect_rows('availability',source,db,apply=True)
            with db: db.execute("UPDATE allocations SET status='Liberada' WHERE reservation_id='r'")
            with db: self.assertEqual(inspect_rows('availability',source,db,apply=True)['allocations']['copiados'],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM allocations WHERE status='Liberada'").fetchone()[0],2)

    def test_inventory_snapshot_adds_order_without_changing_allocations(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with closing(sqlite3.connect(root/'availability.sqlite3')) as db:
                db.executescript('CREATE TABLE inventory(room_id TEXT PRIMARY KEY,total INTEGER);CREATE TABLE allocations(reservation_id TEXT PRIMARY KEY,room_id TEXT,checkin TEXT,checkout TEXT,status TEXT);')
                db.executemany('INSERT INTO inventory VALUES (?,?)',[('z',1),('a',2)])
                db.execute("INSERT INTO allocations VALUES ('unknown','','','','Liberada')")
                db.commit()
            snapshot=snapshot_sources(root,backup=True,services=['availability'])['availability']
            self.assertEqual([(row['room_id'],row['sort_order']) for row in snapshot['inventory']],[('z',0),('a',1)])
            self.assertNotIn('sort_order',snapshot['allocations'][0])
    def test_catalog_and_rooms_keep_original_order_without_changing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, table, column in [('catalog','hotels','document'),('rooms','rooms','name')]:
                with closing(sqlite3.connect(root/(name+'.sqlite3'))) as db:
                    db.execute(f'CREATE TABLE {table}(id TEXT PRIMARY KEY,{column} TEXT)')
                    db.executemany(f'INSERT INTO {table} VALUES (?,?)',[('z-first','first'),('a-second','second')])
                    db.commit()
            snapshot = snapshot_sources(root,backup=True,services=['catalog','rooms'])
            self.assertEqual(list(snapshot),['catalog','rooms'])
            for name,table in [('catalog','hotels'),('rooms','rooms')]:
                self.assertEqual([(row['id'],row['sort_order']) for row in snapshot[name][table]], [('z-first',0),('a-second',1)])
                with closing(sqlite3.connect(root/(name+'.sqlite3'))) as db:
                    self.assertNotIn('sort_order',[column[1] for column in db.execute(f'PRAGMA table_info({table})')])

    def test_room_migration_preserves_camelcase_price_and_rejects_changes(self):
        source = {'rooms':[dict(id='room-a',hotelId='hotel-a',name='Doble',capacity=2,price=300000,sort_order=0)]}
        with closing(sqlite3.connect(':memory:')) as db:
            db.row_factory=sqlite3.Row
            db.execute('CREATE TABLE rooms(id TEXT PRIMARY KEY,"hotelId" TEXT,name TEXT,capacity INTEGER,price INTEGER,sort_order INTEGER)')
            with db: inspect_rows('rooms',source,db,apply=True)
            self.assertEqual(dict(db.execute('SELECT * FROM rooms').fetchone()),source['rooms'][0])
            with db: self.assertEqual(inspect_rows('rooms',source,db,apply=True)['rooms']['copiados'],0)
            conflict={'rooms':[{**source['rooms'][0],'price':1}]}
            with self.assertRaises(ValueError):
                with db: inspect_rows('rooms',conflict,db,apply=True)
            self.assertEqual(db.execute('SELECT price FROM rooms').fetchone()[0],300000)

    def test_backup_preserves_source_and_skips_expired_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with closing(sqlite3.connect(root/'auth.sqlite3')) as db:
                db.execute('CREATE TABLE sessions(token_hash TEXT,user_id TEXT,expires REAL)')
                db.executemany('INSERT INTO sessions VALUES (?,?,?)', [('old','fixture',1),('valid','fixture',time.time()+3600)])
                db.commit()
            snapshots = snapshot_sources(root,backup=True)
            self.assertEqual([row['token_hash'] for row in snapshots['auth']['sessions']],['valid'])
            for path in (root/'auth.sqlite3',next((root/'backups').rglob('auth.sqlite3'))):
                with closing(sqlite3.connect(path)) as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],2)

    def test_repeated_copy_preserves_processed_events(self):
        source = {'users':[user()], 'outbox':[dict(id='welcome:fixture',body='{}',attempts=0,next_try=0,delivered=0)]}
        with closing(target()) as db:
            with db:
                inspect_rows('auth',source,db,apply=True)
                db.execute('UPDATE outbox SET delivered=1,attempts=2')
            with db:
                report = inspect_rows('auth',source,db,apply=True)
            self.assertEqual(report['users']['copiados'],0)
            self.assertEqual(report['outbox']['copiados'],0)
            self.assertEqual(tuple(db.execute('SELECT delivered,attempts FROM outbox').fetchone()),(1,2))

    def test_conflict_rolls_back_other_rows_without_overwrite(self):
        with closing(target()) as db:
            with db:
                inspect_rows('auth',{'users':[user()]},db,apply=True)
            conflict = {**user(),'password_hash':'different-hash'}
            with self.assertRaises(ValueError):
                with db:
                    inspect_rows('auth',{'users':[user('new-fixture'),conflict]},db,apply=True)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT password_hash FROM users').fetchone()[0],'hash')


if __name__ == '__main__':
    unittest.main()
