"""Promueve una cuenta existente por un canal local, sin contraseñas predeterminadas."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'services')]
from start import load_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email',required=True)
    options = parser.parse_args()
    load_environment()
    from common import connect
    with connect('auth') as db:
        row = db.execute('SELECT id,active FROM users WHERE email=?',(options.email.strip().lower(),)).fetchone()
        if not row or not row['active']:
            raise SystemExit('Registra primero una cuenta activa en Hotels con ese correo.')
        db.execute("UPDATE users SET role='admin' WHERE id=?",(row['id'],))
        db.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
    print('Cuenta promovida. Inicia sesión nuevamente para acceder a Administración.')


if __name__ == '__main__':
    main()
