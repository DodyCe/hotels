"""Construye y prueba siete contenedores aislados, sin credenciales ni correo real."""
import http.cookiejar
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    project='hotels-verify-'+uuid.uuid4().hex[:12]
    env=os.environ.copy()
    for key in list(env):
        if key.endswith('_DATABASE_URL') or key.startswith(('SMTP_','GMAIL_')) or key in ('PUBLIC_ORIGIN','INTERNAL_API_KEY','HOTELS_HTTP_PORT','MAIL_PROVIDER','RENDER','ORIGIN_SECRET'):
            env.pop(key)
    port=os.environ.get('COMPOSE_TEST_PORT','18090')
    base='http://127.0.0.1:'+port
    checks=[]
    with tempfile.TemporaryDirectory(prefix='hotels-compose-') as directory:
        config=Path(directory)/'compose.env'
        config.write_text('INTERNAL_API_KEY='+secrets.token_urlsafe(48)+'\nHOTELS_HTTP_PORT='+port+'\nPUBLIC_ORIGIN='+base+'\nCOOKIE_SECURE=0\n'+''.join(k+'=\n' for k in ('AUTH_DATABASE_URL','NOTIFICATIONS_DATABASE_URL','RESERVATIONS_DATABASE_URL','CATALOG_DATABASE_URL','ROOMS_DATABASE_URL','AVAILABILITY_DATABASE_URL','SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM')),encoding='utf-8')
        command=['docker','compose','--project-name',project,'--env-file',str(config)]
        def compose(*args):return subprocess.run([*command,*args],cwd=ROOT,env=env,check=True,capture_output=True,text=True).stdout
        def client():return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        def request(opener,path,body=None,method=None):
            raw=json.dumps(body).encode() if body is not None else None
            req=urllib.request.Request(base+path,data=raw,headers={'Content-Type':'application/json'},method=method)
            try:response=opener.open(req,timeout=15)
            except urllib.error.HTTPError as error:response=error
            with response:return response.status,json.load(response)
        def check(value,label):
            assert value,label
            checks.append(label)
        try:
            compose('version')
            compose('up','--build','--detach','--wait','--wait-timeout','240')
            raw=compose('ps','--format','json').strip()
            records=json.loads(raw) if raw.startswith('[') else [json.loads(line) for line in raw.splitlines()]
            check(len(records)==7 and all(r.get('Health')=='healthy' for r in records),'Siete contenedores sanos: Gateway y seis microservicios')
            guest,admin=client(),client()
            password=secrets.token_urlsafe(24)
            email='docker-'+uuid.uuid4().hex+'@example.test'
            check(request(guest,'/api/auth/register',{'name':'Huésped Docker','email':email,'password':password})[0]==201,'Registro y sesión entre contenedores')
            check(request(guest,'/api/guests')[0]==403,'Administración rechazada para huéspedes')
            start='2100-01-10';end='2100-01-12'
            code,data=request(guest,'/api/reservations',{'roomId':'ghl-monteria-principal','checkin':start,'checkout':end,'guests':2})
            check(code==201 and data['reservation']['status']=='Confirmada','Reserva e inventario coordinados en Docker')
            rid=data['reservation']['id']
            code,data=request(guest,'/api/reservations/'+rid+'/cancel',{})
            check(code==200 and data['status']=='Cancelada','Cancelación y liberación de inventario en Docker')
            compose('exec','-T','auth','python','tools/set_admin.py','--email',email)
            check(request(guest,'/api/auth/me')[0]==401,'La promoción por operador revoca las sesiones anteriores')
            check(request(admin,'/api/auth/login',{'email':email,'password':password})[0]==200,'Acceso administrativo tras nueva sesión')
            code,data=request(admin,'/api/hotels',{'name':'Hotel Docker','area':'Centro','address':'Calle 1','description':'Registro aislado de validación Docker.','source':'https://example.test'})
            check(code==201,'Alta administrativa de hotel desde Docker')
            hid=data['hotel']['id']
            code,data=request(admin,'/api/rooms',{'hotelId':hid,'name':'Doble Docker','capacity':2,'price':100000,'total':2})
            check(code==201 and data['room']['inventory_ready'],'Alta de habitación e inventario por red interna Docker')
            check(request(admin,'/api/hotels/'+hid,method='DELETE')[0]==200,'Retiro lógico administrativo en Docker')
            check('/guests' in request(admin,'/openapi.json')[1]['paths'],'Contrato público administrativo disponible en Docker')
            check('/internal/allocate' in request(admin,'/openapi-internal.json')[1]['paths'],'Contrato interno disponible en Docker')
            with urllib.request.urlopen(base+'/vendor/swagger-ui-bundle.js',timeout=15) as response:
                check(response.status==200 and response.headers.get('Content-Encoding')=='gzip','Swagger UI se sirve desde la propia imagen Docker')
            uid=request(admin,'/api/auth/me')[1]['user']['id']
            check(request(admin,'/api/auth/forgot-password',{'email':email})[0]==202,'Recuperación disponible entre contenedores')
            token='';deadline=time.monotonic()+25
            while time.monotonic()<deadline and not token:
                code=("import re,sqlite3\nwith sqlite3.connect('file:/data/notifications.sqlite3?mode=ro',uri=True) as db:\n"
                      " row=db.execute(\"SELECT body FROM messages WHERE user_id=? AND id LIKE ? ORDER BY created DESC LIMIT 1\",("+repr(uid)+",'password-reset:%')).fetchone()\n"
                      " match=re.search(r'#token=([A-Za-z0-9_-]{43})',row[0]) if row else None\n print(match.group(1) if match else '')")
                token=compose('exec','-T','notifications','python','-c',code).strip()
                if not token:time.sleep(.2)
            check(bool(re.fullmatch(r'[A-Za-z0-9_-]{43}',token)),'Auth entrega el enlace privado a Notificaciones en Docker')
            check(not any(n['id'].startswith('password-reset:') for n in request(admin,'/api/notifications')[1]['notifications']),'El correo de recuperación queda fuera de la bandeja web en Docker')
            new_password=secrets.token_urlsafe(24)
            reset={'token':token,'password':new_password,'confirmPassword':new_password}
            check(request(admin,'/api/auth/reset-password',reset)[0]==200 and request(admin,'/api/auth/me')[0]==401,'La recuperación cambia la contraseña y revoca la sesión en Docker')
            check(request(admin,'/api/auth/login',{'email':email,'password':new_password})[0]==200 and request(admin,'/api/auth/reset-password',reset)[0]==400,'La nueva contraseña funciona y el enlace no se reutiliza en Docker')
            print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=True,indent=2))
        except Exception:
            print(compose('logs','--tail','60'))
            raise
        finally:
            # Solo el proyecto aleatorio creado por esta ejecución; nunca la instancia del usuario.
            compose('down','--volumes','--remove-orphans')


if __name__=='__main__':
    main()
