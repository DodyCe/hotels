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
        CREATE TABLE users(id TEXT PRIMARY KEY,name TEXT,email TEXT UNIQUE,salt TEXT,password_hash TEXT,created REAL);
        CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id TEXT,expires REAL);
        CREATE TABLE outbox(id TEXT PRIMARY KEY,body TEXT,attempts INTEGER,next_try REAL,delivered INTEGER);
    ''')
    return db


def user(identifier='fixture'):
    return dict(id=identifier,name='Prueba',email=identifier+'@example.test',salt='salt',password_hash='hash',created=1.25)


class Migration(unittest.TestCase):
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
