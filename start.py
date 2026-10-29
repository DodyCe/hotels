"""Arranca seis microservicios y migra reservas antes de abrir el Gateway."""
import argparse
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVICE_SPECS = [('services/auth.py',8101),('services/notifications.py',8102),
                 ('services/reservations.py',8103),('services/catalog.py',8104),
                 ('services/rooms.py',8105),('services/availability.py',8106)]

def load_environment():
    config = ROOT / '.env'
    if config.exists():
        for line in config.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    data = Path(os.environ.get('HOTELS_DATA_DIR', str(ROOT / 'data')))
    data.mkdir(parents=True, exist_ok=True)
    key_file = data / '.internal-key'
    if not os.environ.get('INTERNAL_API_KEY'):
        if not key_file.exists():
            key_file.write_text(secrets.token_urlsafe(48), encoding='utf-8')
        os.environ['INTERNAL_API_KEY'] = key_file.read_text(encoding='utf-8').strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--open', action='store_true', help='Abre la web en el navegador')
    options = parser.parse_args()
    load_environment()
    from services.postgres import validate_configuration
    validate_configuration()
    processes = []
    try:
        for path, port in SERVICE_SPECS:
            env = service_environment(path)
            env['PYTHONUNBUFFERED'] = '1'
            if port:
                env['PORT'] = str(port)
            processes.append(subprocess.Popen([sys.executable, str(ROOT/path)], cwd=ROOT, env=env))
        for _ in range(50):
            if any(p.poll() is not None for p in processes):
                raise RuntimeError('Un servicio no pudo iniciar. Revisa los puertos 8080 y 8101–8106.')
            try:
                for _,port in SERVICE_SPECS:
                    urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=6).close()
                break
            except (OSError, urllib.error.URLError):
                time.sleep(.2)
        else:
            raise RuntimeError('No se pudo comprobar el inicio de todos los servicios.')
        request = urllib.request.Request('http://127.0.0.1:8103/internal/reconcile',data=b'{}',
            headers={'Content-Type':'application/json','X-Internal-Key':os.environ['INTERNAL_API_KEY']})
        with urllib.request.urlopen(request,timeout=25) as response:
            import json
            if json.load(response)['pending']:
                raise RuntimeError('Hay reservas pendientes de migración. No se abre el Gateway para proteger sus cupos.')
        processes.append(subprocess.Popen([sys.executable,str(ROOT/'gateway.py')],cwd=ROOT,env=service_environment('gateway.py')))
        url = f"http://127.0.0.1:{os.environ.get('GATEWAY_PORT','8080')}"
        for _ in range(30):
            if processes[-1].poll() is not None:
                raise RuntimeError('No pudo iniciar el Gateway. Comprueba el puerto 8080.')
            try:
                urllib.request.urlopen(url+'/health',timeout=.4).close()
                break
            except OSError:
                time.sleep(.2)
        else:
            raise RuntimeError('El Gateway no respondió a tiempo.')
        print('\nHOTELS · Sistema de reservas\n' + url + '\nCtrl+C para cerrar todos los servicios.\n', flush=True)
        if options.open:
            webbrowser.open(url)
        while all(p.poll() is None for p in processes):
            time.sleep(.5)
    except KeyboardInterrupt:
        print('\nCerrando Hotels...', flush=True)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

def service_environment(path):
    """Cada proceso recibe únicamente su conexión y los secretos que le pertenecen."""
    env = os.environ.copy()
    owned = {'services/auth.py': 'AUTH_DATABASE_URL',
             'services/notifications.py': 'NOTIFICATIONS_DATABASE_URL',
             'services/catalog.py': 'CATALOG_DATABASE_URL',
             'services/rooms.py': 'ROOMS_DATABASE_URL',
             'services/reservations.py': 'RESERVATIONS_DATABASE_URL',
             'services/availability.py': 'AVAILABILITY_DATABASE_URL'}.get(path)
    for key in ('AUTH_DATABASE_URL', 'NOTIFICATIONS_DATABASE_URL', 'CATALOG_DATABASE_URL', 'ROOMS_DATABASE_URL',
                'RESERVATIONS_DATABASE_URL', 'AVAILABILITY_DATABASE_URL'):
        if key != owned:
            env.pop(key, None)
    if path != 'services/notifications.py':
        for key in list(env):
            if key.startswith(('SMTP_','GMAIL_')) or key == 'MAIL_PROVIDER':
                env.pop(key)
    if path != 'gateway.py':
        env.pop('ORIGIN_SECRET',None)
    env.pop('HOTELS_GATEWAY_URL',None)
    return env


if __name__ == '__main__':
    main()
