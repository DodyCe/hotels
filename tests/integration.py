import concurrent.futures
import datetime as dt
import http.cookiejar
import json
import sqlite3
import time
import uuid
from contextlib import closing
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'http://127.0.0.1:18080'
PORTS = tuple(range(18101,18107))
INTERNAL_KEY = ''
CONTROLLER = None
checks = []
USE_POSTGRES = False
POSTGRES_SERVICES = set()
FIXTURE_USERS = set()
RUN_TAG = uuid.uuid4().hex
LEGACY_IDS = ('LEGACY-'+RUN_TAG+'-A', 'LEGACY-'+RUN_TAG+'-C')
LEGACY_USER = 'legacy-'+RUN_TAG
FIXTURE_ALLOCATION_IDS = set(LEGACY_IDS)
TEST_DATE_BASE = dt.date(2100,1,1)+dt.timedelta(days=int(RUN_TAG[:6],16)%6000)
def client():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def request(opener, path, data=None, headers=None, method=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE+path, data=body, headers={'Content-Type':'application/json', **(headers or {})},method=method)
    try: response = opener.open(req, timeout=15)
    except urllib.error.HTTPError as error: response = error
    with response:
        result = json.load(response)
        if path == '/api/auth/register' and response.code == 201:
            FIXTURE_USERS.add(result['user']['id'])
        return response.code, result, response.headers
def check(condition, label):
    assert condition, label
    checks.append(label)


import os
import secrets
import socket
import subprocess
import sys
import tempfile

def run_checks(data_dir):
    a, b, anonymous = client(),client(),client()
    suffix = str(time.time_ns())
    email_a = f'estudiante-{suffix}@example.test'
    password = 'Practica-Hotels-2026!'
    code,data,headers = request(a,'/api/auth/register',{'name':'Estudiante A','email':email_a,'password':password})
    check(code == 201, 'Registro de cuenta con sesión')
    check('HttpOnly' in headers.get('Set-Cookie','') and 'SameSite=Strict' in headers.get('Set-Cookie',''), 'Cookie HttpOnly y SameSite')
    uid = data['user']['id']
    check(request(a,'/api/auth/me')[1]['user']['email'] == email_a, 'Perfil autenticado y correo persistido')
    check(request(b,'/api/auth/register',{'name':'Estudiante B','email':f'otro-{suffix}@example.test','password':password})[0] == 201,'Segunda cuenta independiente')
    check(request(anonymous,'/api/reservations')[0] == 401,'Rechazo de consultas sin sesión')
    check(request(anonymous,'/api/auth/login',{'email':email_a,'password':'Incorrecta-2026!'})[0] == 401,'Contraseña incorrecta rechazada')
    check(request(anonymous,'/api/auth/login',{'email':email_a,'password':password})[0] == 200,'Inicio de sesión con contraseña correcta')
    check(request(client(),'/api/auth/register',{'name':'Duplicado','email':email_a,'password':password})[0] == 409,'Correo duplicado rechazado')
    check(request(a,'/api/auth/logout',{}, {'Origin':'https://externo.invalid'})[0] == 403,'Origen externo rechazado')
    check(request(a,'/api/internal/events',{})[0] == 404,'Eventos internos no expuestos en gateway')
    start = TEST_DATE_BASE+dt.timedelta(days=40)
    end = start+dt.timedelta(days=3)
    payload = {'hotelId':'ghl-monteria','roomId':'ghl-monteria-principal','checkin':start.isoformat(),'checkout':end.isoformat(),'guests':2,'total':1,'email':'ajeno@example.test'}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(a,'/api/reservations',payload),range(2)))
    check(sorted(r[0] for r in results) == [201,409], 'Concurrencia: solo una reserva para un mismo cupo')
    reservation = next(r[1]['reservation'] for r in results if r[0] == 201)
    rid = reservation['id']
    check(reservation['total'] == 1050000,'Precio calculado por el servidor; ignora total del cliente')
    check(request(b,'/api/reservations')[1]['reservations'] == [],'Aislamiento de reservas entre usuarios')
    check(request(b,f'/api/reservations/{rid}/cancel',{})[0] == 404,'Otra cuenta no puede cancelar la reserva')
    check(available(a,'ghl-monteria-principal',start,end) == 0,'Inventario bloqueado después de reservar')
    check(request(a,f'/api/reservations/{rid}/cancel',{})[0] == 200,'Cancelación por el propietario')
    check(request(a,f'/api/reservations/{rid}/cancel',{})[0] == 200,'Cancelación idempotente')
    check(available(a,'ghl-monteria-principal',start,end) == 1,'Inventario liberado tras cancelación')
    invalid = {**payload,'checkout':start.isoformat()}
    check(request(a,'/api/reservations',invalid)[0] == 400,'Fechas inválidas rechazadas')
    deadline = time.monotonic()+12
    while time.monotonic()<deadline:
        messages = request(a,'/api/notifications')[1]['notifications']
        if len(messages) >= 3: break
        time.sleep(.3)
    check(len(messages) == 3,'Bienvenida, confirmación y cancelación llegan a Notificaciones')
    check(all(m['recipient'] == email_a for m in messages),'Destinatario obtenido en Auth; ignora correo enviado por cliente')
    check(len({m['id'] for m in messages}) == 3,'Sin duplicados al repetir cancelación')
    check(all(m['status'] == 'vista_previa' for m in messages),'SMTP sin configurar: vista previa sin envío real')
    check(all('No constituye una reserva real' in m['body'] for m in messages),'Aviso académico en todos los correos')
    if USE_POSTGRES:
        import postgres
        with postgres.connect('auth') as db:
            row = db.execute('SELECT salt,password_hash FROM users WHERE id=?',(uid,)).fetchone()
            saved = (row['salt'],row['password_hash'])
    else:
        with closing(sqlite3.connect(Path(data_dir) / 'auth.sqlite3')) as db:
            saved = db.execute('SELECT salt,password_hash FROM users WHERE id=?',(uid,)).fetchone()
    check(len(saved[0]) == 32 and len(saved[1]) == 64 and password not in saved,'Contraseña persistida con sal y scrypt')
    check(request(a,'/api/auth/logout',{})[0] == 200 and request(a,'/api/reservations')[0] == 401,'Cierre de sesión revoca acceso')
    advanced_checks(a,b,data_dir,password,email_a)
    inventory_concurrency_checks(a,password,email_a)
    admin_checks(a,data_dir,password,email_a)
    print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False,indent=2))


def admin_checks(customer,data_dir,password,email):
    request(customer,'/api/auth/login',{'email':email,'password':password})
    check(request(customer,'/api/guests')[0]==403,'Una cuenta normal no puede consultar huéspedes')
    check(request(customer,'/api/hotels?includeInactive=true')[0]==403,'Los registros inactivos requieren administración')
    check(request(customer,'/api/hotels',{})[0]==403,'Una cuenta normal no puede crear hoteles')
    check(request(client(),'/api/auth/register',{'name':'Escalada','email':'escalada-'+RUN_TAG+'@example.test','password':password,'role':'admin'})[0]==400,'El registro público no acepta roles de administrador')
    admin=client()
    admin_email='admin-'+RUN_TAG+'@example.test'
    code,result,_=request(admin,'/api/auth/register',{'name':'Administrador de prueba','email':admin_email,'password':password})
    assert code==201
    uid=result['user']['id']
    if USE_POSTGRES:
        import postgres
        with postgres.connect('auth') as db:
            db.execute("UPDATE users SET role='admin' WHERE id=?",(uid,))
    else:
        with closing(sqlite3.connect(Path(data_dir)/'auth.sqlite3')) as db:
            db.execute("UPDATE users SET role='admin' WHERE id=?",(uid,));db.commit()
    check(request(admin,'/api/auth/me')[1]['user']['role']=='admin','Auth resuelve el rol actual en el servidor')
    check(request(admin,'/api/guests')[0]==200,'El administrador puede consultar los perfiles de huéspedes')
    if USE_POSTGRES:
        # CRUD completo se ejecuta en SQLite aislado y Docker; no deja hoteles de prueba en las bases compartidas.
        return
    hotel={'name':'Hotel de validación','area':'Centro','address':'Calle de validación 1','description':'Hotel temporal de las pruebas de administración.','source':'https://example.test','tags':['wifi'],'amenities':['Wi-Fi']}
    code,result,_=request(admin,'/api/hotels',hotel)
    check(code==201,'Administración crea un hotel por el Gateway')
    hid=result['hotel']['id']
    check(request(admin,'/api/hotels/'+hid,{'name':'Hotel actualizado'},method='PATCH')[1]['hotel']['name']=='Hotel actualizado','Administración edita hoteles con PATCH')
    check(request(admin,'/api/hotels/'+hid,{'name':'<script>alert(1)</script>'},method='PATCH')[0]==400,'Se rechaza HTML en los campos administrativos')
    code,result,_=request(admin,'/api/rooms',{'hotelId':hid,'name':'Doble de prueba','capacity':2,'price':111000,'total':2})
    check(code==201 and result['room']['inventory_ready'],'El alta de habitación crea su inventario mediante API')
    room=result['room']['id']
    check(request(customer,'/api/rooms/'+room,{'price':1},method='PATCH')[0]==403,'Una cuenta normal no puede cambiar tarifas')
    check(request(admin,'/api/rooms/'+room,{'name':'Doble actualizada','price':120000},method='PATCH')[1]['room']['price']==120000,'Administración edita características y tarifa')
    start=TEST_DATE_BASE+dt.timedelta(days=280)
    booking={'roomId':room,'checkin':str(start),'checkout':str(start+dt.timedelta(days=2)),'guests':2}
    first=request(customer,'/api/reservations',booking)
    second=request(customer,'/api/reservations',booking)
    check(first[0]==second[0]==201 and first[1]['reservation']['total']==240000,'Las habitaciones administradas se reservan y usan la tarifa del servidor')
    check(request(admin,'/api/inventory/'+room,{'total':1},method='PUT')[0]==409,'Inventario rechaza reducciones que causarían sobreventa')
    check(request(customer,'/api/inventory/'+room,{'total':3},method='PUT')[0]==403,'Solo administración puede ajustar unidades')
    check(request(admin,'/api/inventory/'+room,{'total':3},method='PUT')[1]['inventory']['total']==3,'Administración ajusta unidades en el servicio de Inventario')
    check(request(admin,'/api/rooms/'+room,method='DELETE')[1]['room']['active'] is False,'Retirar una habitación conserva el registro histórico')
    check(request(customer,'/api/rooms/'+room)[0]==404,'Las habitaciones inactivas no se ofrecen al público')
    check(request(admin,'/api/rooms/'+room,{'active':True},method='PATCH')[1]['room']['active'],'Una habitación se puede reactivar')
    check(request(admin,'/api/hotels/'+hid,method='DELETE')[1]['hotel']['active'] is False,'Administración retira hoteles sin borrar reservas')
    check(request(customer,'/api/reservations',booking)[0]==404,'No se admiten reservas nuevas en hoteles retirados')
    check(request(admin,'/api/hotels/'+hid,{'active':True},method='PATCH')[1]['hotel']['active'],'Un hotel se puede reactivar')
    for created in (first,second):request(customer,'/api/reservations/'+created[1]['reservation']['id']+'/cancel',{})
    code,result,_=request(admin,'/api/guests',{'name':'Huésped sin cuenta','email':'invitado-'+RUN_TAG+'@example.test','phone':'3001234567'})
    check(code==201 and result['guest']['user_id'] is None,'Se registra un huésped sin crear credenciales ni sesión')
    gid=result['guest']['id']
    check(request(admin,'/api/guests/'+gid,{'name':'Huésped actualizado'},method='PATCH')[1]['guest']['name']=='Huésped actualizado','Se editan los datos de un huésped')
    check(request(admin,'/api/guests/'+gid,method='DELETE')[1]['guest']['active'] is False,'Retirar un huésped conserva sus datos históricos')
    check(request(admin,'/api/guests/'+gid,{'active':True},method='PATCH')[1]['guest']['active'],'Un huésped se puede reactivar')
    check(request(admin,'/api/guests/'+uid,method='DELETE')[0]==409,'No se puede desactivar una cuenta administradora como huésped')
    account=client();account_email='guest-'+RUN_TAG+'@example.test'
    uid=request(account,'/api/auth/register',{'name':'Cuenta desactivable','email':account_email,'password':password})[1]['user']['id']
    request(admin,'/api/guests/'+uid,method='DELETE')
    check(request(account,'/api/auth/me')[0]==401,'Desactivar un huésped vinculado revoca sus sesiones')
    check(request(client(),'/api/auth/login',{'email':account_email,'password':password})[0]==403,'Una cuenta inactiva no puede iniciar sesión')
    CONTROLLER('stop',18106)
    code,result,_=request(admin,'/api/rooms',{'hotelId':hid,'name':'Alta recuperable','capacity':2,'price':100000,'total':1})
    check(code==202 and not result['room']['inventory_ready'],'La caída de Inventario conserva un alta pendiente, sin ofrecer cupos ficticios')
    pending=result['room']['id']
    CONTROLLER('start',18106)
    check(poll(lambda:request(customer,'/api/rooms/'+pending)[0]==200,timeout=15),'El alta pendiente se recupera al volver Inventario')
    with urllib.request.urlopen(BASE+'/openapi.json') as response:spec=json.load(response)
    check('/guests' in spec['paths'] and 'patch' in spec['paths']['/hotels/{hotelId}'],'OpenAPI publica los contratos administrativos')
    with urllib.request.urlopen(BASE+'/openapi-internal.json') as response:spec=json.load(response)
    check('/internal/inventory' in spec['paths'] and '/internal/allocate' in spec['paths'],'OpenAPI documenta la comunicación interna sin exponerla en el Gateway')



def available(opener,room,start,end):
    data=request(opener,f'/api/availability?checkin={start}&checkout={end}')[1]
    return next(r['available'] for r in data['availability'] if r['roomId']==room)

def internal(port,path,data=None,opener=None):
    if path in ('/internal/allocate','/internal/release') and data:
        FIXTURE_ALLOCATION_IDS.add(data['reservationId'])
    body=json.dumps(data).encode() if data is not None else None
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=body,headers={'X-Internal-Key':INTERNAL_KEY,'Content-Type':'application/json'})
    try: response=(opener.open if opener else urllib.request.urlopen)(req,timeout=15)
    except urllib.error.HTTPError as error: response=error
    with response: return response.code,json.load(response)

def poll(predicate,timeout=12):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate(): return True
        time.sleep(.2)
    return False

def advanced_checks(a,b,data_dir,password,email_a):
    catalog=request(b,'/api/hotels')[1]['hotels']
    check(len(catalog)==3 and all('price' not in h and 'capacity' not in h for h in catalog),'Hoteles expone catálogo sin apropiarse de habitaciones o precios')
    room_data=request(b,'/api/rooms')[1]['rooms']
    check(len(room_data)==6,'Habitaciones expone seis tipos de práctica independientes')
    check(len(request(b,'/api/rooms?hotelId=ghl-monteria')[1]['rooms'])==2,'Filtrado de habitaciones por hotel')
    check(all(r['capacity']>=4 for r in request(b,'/api/rooms?guests=4')[1]['rooms']),'Filtrado de habitaciones por capacidad')
    check(request(b,'/api/rooms/inexistente')[0]==404 and request(b,'/api/hotels/inexistente')[0]==404,'Recursos inexistentes devuelven 404')
    check(request(b,'/api/rooms?guests=0')[0]==400,'Habitaciones valida el filtro de huéspedes')
    check(len(request(b,'/api/inventory')[1]['inventory'])==6,'Inventario gestiona un registro por tipo de habitación')
    with urllib.request.urlopen('http://127.0.0.1:18104/health') as response:
        check(json.load(response)['service']=='catalogo-hoteles','Catálogo tiene proceso y health propios')
    check(internal(18105,'/health')[1]['service']=='habitaciones','Habitaciones tiene proceso y health propios')
    check(internal(18106,'/health')[1]['service']=='disponibilidad-inventario','Inventario tiene proceso y health propios')
    files={f.name for f in Path(data_dir).glob('*.sqlite3')}
    if USE_POSTGRES:
        service_ports = {'auth':18101, 'notifications':18102, 'reservations':18103, 'catalog':18104, 'rooms':18105,'availability':18106}
        sqlite_services = {'auth','notifications','catalog','rooms','reservations','availability'} - POSTGRES_SERVICES
        check({name+'.sqlite3' for name in sqlite_services} <= files
              and not {name+'.sqlite3' for name in POSTGRES_SERVICES} & files
              and all(internal(service_ports[name],'/health')[1].get('database')=='postgresql' for name in POSTGRES_SERVICES),
              f'{len(POSTGRES_SERVICES)} PostgreSQL y {len(sqlite_services)} SQLite independientes, sin respaldo silencioso')
    else:
        check({'auth.sqlite3','notifications.sqlite3','reservations.sqlite3','catalog.sqlite3','rooms.sqlite3','availability.sqlite3'}<=files,'Seis bases de datos separadas')
    migrated_start=TEST_DATE_BASE+dt.timedelta(days=100)
    migrated_end=migrated_start+dt.timedelta(days=3)
    check(available(b,'ghl-monteria-principal',migrated_start,migrated_end)==0,'Reserva antigua confirmada bloquea el inventario migrado')
    check(internal(18103,'/internal/reconcile',{})[1]['pending']==0,'Repetir migración no duplica cupos ni deja operaciones pendientes')
    if 'reservations' in POSTGRES_SERVICES:
        import postgres
        with postgres.connect('reservations') as db:
            row=db.execute('SELECT status,room_id,hotel_name,total FROM reservations WHERE id=?',(LEGACY_IDS[0],)).fetchone()
            old=tuple(row[column] for column in ('status','room_id','hotel_name','total'))
            cancelled=(db.execute('SELECT status FROM reservations WHERE id=?',(LEGACY_IDS[1],)).fetchone()['status'],)
    else:
        with closing(sqlite3.connect(Path(data_dir)/'reservations.sqlite3')) as db:
            old=db.execute('SELECT status,room_id,hotel_name,total FROM reservations WHERE id=?',(LEGACY_IDS[0],)).fetchone()
            cancelled=db.execute('SELECT status FROM reservations WHERE id=?',(LEGACY_IDS[1],)).fetchone()
    check(old==('Confirmada','ghl-monteria-principal','GHL Hotel Montería',1050000) and cancelled[0]=='Cancelada','Migración conserva reservas confirmadas, canceladas y sus importes')
    future=TEST_DATE_BASE+dt.timedelta(days=65)
    end=future+dt.timedelta(days=3)
    principal={'hotelId':'ghl-monteria','roomId':'ghl-monteria-principal','checkin':str(future),'checkout':str(end),'guests':2}
    check(request(b,'/api/reservations',{**principal,'hotelId':'sites-monteria'})[0]==400,'Reservas rechaza una habitación asociada a otro hotel')
    check(request(b,'/api/reservations',{**principal,'roomId':'sites-monteria-principal','hotelId':'sites-monteria','guests':4})[0]==400,'Reservas valida la capacidad usando Habitaciones')
    check(request(b,'/api/reservations',{**principal,'checkin':future.strftime('%Y%m%d')})[0]==400,'Se rechazan fechas fuera del formato canónico')
    code,data,_=request(b,'/api/reservations',principal)
    check(code==201,'Reserva principal confirmada mediante APIs separadas')
    first=data['reservation']['id']
    alternative={**principal,'roomId':'ghl-monteria-alternativa'}
    code,data,_=request(b,'/api/reservations',alternative)
    check(code==201,'Otro tipo de habitación del mismo hotel conserva su cupo')
    second=data['reservation']['id']
    check(data['reservation']['total']==900000,'Reservas obtiene la tarifa del tipo elegido en Habitaciones')
    check(internal(18106,'/internal/allocate',{'reservationId':first,'roomId':'ghl-monteria-principal','checkin':str(future),'checkout':str(end)})[0]==200,'Reintento de asignación con el mismo identificador es idempotente')
    check(request(b,f'/api/reservations/{first}/cancel',{})[0]==200,'Cancelación libera el tipo principal por API de Inventario')
    check(available(b,'ghl-monteria-principal',future,end)==1 and available(b,'ghl-monteria-alternativa',future,end)==0,'Liberar un tipo no altera el inventario de otro')
    check(internal(18106,'/internal/allocate',{'reservationId':first,'roomId':'ghl-monteria-principal','checkin':str(future),'checkout':str(end)})[0]==409,'Una asignación tardía no reactiva una reserva liberada')
    request(b,f'/api/reservations/{second}/cancel',{})
    CONTROLLER('stop',18106)
    later=future+dt.timedelta(days=10)
    later_end=later+dt.timedelta(days=3)
    code,data,_=request(b,'/api/reservations',{**principal,'checkin':str(later),'checkout':str(later_end)})
    pending=data['reservation']['id']
    check(code==202 and data['reservation']['status']=='Pendiente','Caída de Inventario conserva la solicitud pendiente')
    CONTROLLER('start',18106)
    def status():
        return next(r['status'] for r in request(b,'/api/reservations')[1]['reservations'] if r['id']==pending)
    check(poll(lambda:status()=='Confirmada'),'La reserva pendiente se confirma al recuperar Inventario')
    check(available(b,'ghl-monteria-principal',later,later_end)==0,'Reconciliación bloquea exactamente un cupo')
    CONTROLLER('stop',18106)
    code,data,_=request(b,f'/api/reservations/{pending}/cancel',{})
    check(code==202 and data['status']=='Cancelando','Caída durante cancelación conserva un estado recuperable')
    CONTROLLER('start',18106)
    check(poll(lambda:status()=='Cancelada'),'La cancelación se completa al recuperar Inventario')
    check(available(b,'ghl-monteria-principal',later,later_end)==1,'Recuperación de cancelación libera el cupo')
    CONTROLLER('stop',18103); CONTROLLER('start',18103)
    check(status()=='Cancelada','Reservas conserva su estado al reiniciar el proceso')
    request(b,'/api/auth/logout',{})

def inventory_concurrency_checks(account,password,email):
    """Dos procesos distintos comparten la misma base; el bloqueo Python no basta."""
    CONTROLLER('start',18206)
    start=TEST_DATE_BASE+dt.timedelta(days=150)
    payload={'roomId':'ghl-monteria-principal','checkin':str(start),'checkout':str(start+dt.timedelta(days=3))}
    ids=['TEST-'+RUN_TAG+'-'+str(index) for index in range(5)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda pair:internal(pair[0],'/internal/allocate',{**payload,'reservationId':pair[1]}),[(18106,ids[0]),(18206,ids[1])]))
    check(sorted(result[0] for result in results)==[201,409],'Dos procesos de Inventario comparten el bloqueo y no sobrevendan')
    for rid in ids[:2]: internal(18106,'/internal/release',{'reservationId':rid})
    same={**payload,'reservationId':ids[2]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda port:internal(port,'/internal/allocate',same),(18106,18206)))
    check(sorted(result[0] for result in results)==[200,201],'Dos instancias asignan el mismo identificador exactamente una vez')
    internal(18206,'/internal/release',{'reservationId':ids[2]})
    check(internal(18106,'/internal/allocate',same)[0]==409,'Una liberación en otra instancia impide reactivar la asignación')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        allocated=pool.submit(internal,18106,'/internal/allocate',{**payload,'reservationId':ids[3]})
        released=pool.submit(internal,18206,'/internal/release',{'reservationId':ids[3]})
        codes=(allocated.result()[0],released.result()[0])
    check(codes[0] in (201,409) and codes[1]==200 and internal(18106,'/internal/allocate',{**payload,'reservationId':ids[3]})[0]==409,
          'Asignación y liberación simultáneas convergen a Liberada')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda pair:internal(pair[0],'/internal/allocate',{**payload,'roomId':pair[1],'reservationId':ids[4]}),[(18106,'ghl-monteria-principal'),(18206,'sites-monteria-principal')]))
    check(sorted(result[0] for result in results)==[201,409],'Un identificador no puede asignarse a habitaciones diferentes desde dos instancias')
    internal(18106,'/internal/release',{'reservationId':ids[4]})
    start=TEST_DATE_BASE+dt.timedelta(days=180)
    code,data,_=request(client(),f'/api/availability?checkin={start}&checkout={start+dt.timedelta(days=30)}')
    check(code==200 and len(data['availability'])==6,'La consulta de treinta noches funciona sin una consulta SQL por noche')
    CONTROLLER('stop',18206)
    if 'reservations' in POSTGRES_SERVICES:
        import postgres
        CONTROLLER('start',18203)
        assert request(account,'/api/auth/login',{'email':email,'password':password})[0]==200
        start=TEST_DATE_BASE+dt.timedelta(days=220)
        code,data,_=request(account,'/api/reservations',{'roomId':'ghl-monteria-principal','checkin':str(start),'checkout':str(start+dt.timedelta(days=2)),'guests':2})
        check(code==201,'Reserva confirmada antes de cancelar desde dos procesos')
        rid=data['reservation']['id']
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda port:internal(port,'/reservations/'+rid+'/cancel',{},account),(18103,18203)))
        check(all(result[0]==200 and result[1]['status']=='Cancelada' for result in results),'Dos instancias de Reservas cancelan simultáneamente sin errores')
        check(available(account,'ghl-monteria-principal',start,start+dt.timedelta(days=2))==1,'La cancelación entre instancias libera el inventario una vez')
        with postgres.connect('reservations') as db:
            count=db.execute('SELECT COUNT(*) AS total FROM outbox WHERE id=?',('cancelled:'+rid,)).fetchone()['total']
        check(count==1,'La cancelación concurrente conserva un único evento en outbox')
        request(account,'/api/auth/logout',{})
        CONTROLLER('stop',18203)


def main():
    global INTERNAL_KEY,CONTROLLER,USE_POSTGRES,POSTGRES_SERVICES
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--postgres',action='store_true',help='Usa las conexiones PostgreSQL de .env; limpia solo sus propias cuentas de prueba.')
    parser.add_argument('--four-postgres',action='store_true',help='Exige Auth, Notificaciones, Catálogo y Habitaciones en PostgreSQL.')
    parser.add_argument('--six-postgres',action='store_true',help='Exige los seis servicios en bases PostgreSQL independientes.')
    options = parser.parse_args()
    USE_POSTGRES=options.postgres or options.four_postgres or options.six_postgres
    root=Path(__file__).resolve().parents[1]
    if USE_POSTGRES:
        sys.path.insert(0,str(root)); sys.path.insert(0,str(root/'services'))
        from start import load_environment
        import postgres
        load_environment()
        required=tuple(postgres.SETTINGS) if options.six_postgres else (('auth','notifications','catalog','rooms') if options.four_postgres else ())
        postgres.validate_configuration(require_both=True, require_services=required)
        POSTGRES_SERVICES = {name for name in postgres.SETTINGS if postgres.database_url(name)}
        # La instancia normal podría consumir los mismos eventos con SMTP habilitado.
        for port in (8080,*range(8101,8107)):
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1',port))==0:
                    raise SystemExit('Detén Hotels antes de las pruebas con PostgreSQL compartido.')
        for name in ('auth','reservations'):
            if name in POSTGRES_SERVICES:
                with postgres.connect(name) as db:
                    if db.execute('SELECT COUNT(*) AS total FROM outbox WHERE delivered=0').fetchone()['total']:
                        raise SystemExit('Hay eventos reales pendientes; no se ejecutan pruebas para no consumirlos.')
                    if name=='reservations' and db.execute("SELECT COUNT(*) AS total FROM reservations WHERE room_id='' OR inventory_synced=0 OR status IN ('Pendiente','Cancelando')").fetchone()['total']:
                        raise SystemExit('Hay reservas reales por reconciliar; no se ejecutan pruebas sobre ellas.')
    for port in (18080,*PORTS,18206,18203):
        with socket.socket() as probe:
            try: probe.bind(('127.0.0.1',port))
            except OSError: raise SystemExit('Puerto de pruebas ocupado: '+str(port)) from None
    with tempfile.TemporaryDirectory(prefix='hotels-tests-') as temp:
        # Fixture con el esquema anterior, sin leer ni alterar los datos del usuario.
        a=TEST_DATE_BASE+dt.timedelta(days=100)
        b=a+dt.timedelta(days=3)
        legacy_rows=[(LEGACY_IDS[0],LEGACY_USER,'ghl-monteria',str(a),str(b),2,1050000,'Confirmada',time.time()),
                     (LEGACY_IDS[1],LEGACY_USER,'sites-monteria',str(a),str(b),2,885000,'Cancelada',time.time())]
        if 'reservations' not in POSTGRES_SERVICES:
            with closing(sqlite3.connect(Path(temp)/'reservations.sqlite3')) as db:
                db.execute('CREATE TABLE reservations (id TEXT PRIMARY KEY,user_id TEXT NOT NULL,hotel_id TEXT NOT NULL,checkin TEXT NOT NULL,checkout TEXT NOT NULL,guests INTEGER NOT NULL,total INTEGER NOT NULL,status TEXT NOT NULL,created REAL NOT NULL)')
                db.executemany('INSERT INTO reservations VALUES (?,?,?,?,?,?,?,?,?)',legacy_rows)
                db.commit()
        env=os.environ.copy()
        INTERNAL_KEY=secrets.token_urlsafe(48)
        env.update(HOTELS_DATA_DIR=temp,INTERNAL_API_KEY=INTERNAL_KEY,
            AUTH_DATABASE_URL=os.environ.get('AUTH_DATABASE_URL','') if USE_POSTGRES else '',
            NOTIFICATIONS_DATABASE_URL=os.environ.get('NOTIFICATIONS_DATABASE_URL','') if USE_POSTGRES else '',
            CATALOG_DATABASE_URL=os.environ.get('CATALOG_DATABASE_URL','') if USE_POSTGRES else '',
            ROOMS_DATABASE_URL=os.environ.get('ROOMS_DATABASE_URL','') if USE_POSTGRES else '',
            RESERVATIONS_DATABASE_URL=os.environ.get('RESERVATIONS_DATABASE_URL','') if USE_POSTGRES else '',
            AVAILABILITY_DATABASE_URL=os.environ.get('AVAILABILITY_DATABASE_URL','') if USE_POSTGRES else '',
            SMTP_HOST='',SMTP_USER='',SMTP_PASSWORD='',SMTP_FROM='',
            GATEWAY_PORT='18080',PUBLIC_ORIGIN='http://127.0.0.1:18080',
            AUTH_URL='http://127.0.0.1:18101',NOTIFICATIONS_URL='http://127.0.0.1:18102',
            RESERVATIONS_URL='http://127.0.0.1:18103',CATALOG_URL='http://127.0.0.1:18104',
            ROOMS_URL='http://127.0.0.1:18105',AVAILABILITY_URL='http://127.0.0.1:18106',
            SERVICE_BIND='127.0.0.1',GATEWAY_BIND='127.0.0.1',COOKIE_SECURE='0',PYTHONDONTWRITEBYTECODE='1')
        files={18101:'services/auth.py',18102:'services/notifications.py',18103:'services/reservations.py',18203:'services/reservations.py',18104:'services/catalog.py',18105:'services/rooms.py',18106:'services/availability.py',18206:'services/availability.py',18080:'gateway.py'}
        processes={}
        with (Path(temp)/'services.log').open('w+',encoding='utf-8') as logs:
            def control(action,port):
                if action=='stop':
                    p=processes[port]
                    if p.poll() is None:p.terminate()
                    try:p.wait(timeout=5)
                    except subprocess.TimeoutExpired:p.kill();p.wait()
                else:
                    child_env={**env,'PORT':str(port)}
                    owner_keys = {18101:'AUTH_DATABASE_URL',18102:'NOTIFICATIONS_DATABASE_URL',18103:'RESERVATIONS_DATABASE_URL',18203:'RESERVATIONS_DATABASE_URL',18104:'CATALOG_DATABASE_URL',18105:'ROOMS_DATABASE_URL',18106:'AVAILABILITY_DATABASE_URL',18206:'AVAILABILITY_DATABASE_URL'}
                    for key in ('AUTH_DATABASE_URL','NOTIFICATIONS_DATABASE_URL','CATALOG_DATABASE_URL','ROOMS_DATABASE_URL','RESERVATIONS_DATABASE_URL','AVAILABILITY_DATABASE_URL'):
                        if key != owner_keys.get(port): child_env.pop(key,None)
                    processes[port]=subprocess.Popen([sys.executable,str(root/files[port])],cwd=root,env=child_env,stdout=logs,stderr=logs)
                    def ready():
                        try:
                            urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=8 if USE_POSTGRES else .3).close();return True
                        except OSError:return False
                    if not poll(ready,timeout=40 if USE_POSTGRES else 15):raise RuntimeError('No inició el servicio de pruebas '+str(port))
            CONTROLLER=control
            try:
                if 'reservations' in POSTGRES_SERVICES:
                    with postgres.connect('reservations') as db:
                        for row in legacy_rows:
                            db.execute('INSERT INTO reservations(id,user_id,hotel_id,checkin,checkout,guests,total,status,created) VALUES (?,?,?,?,?,?,?,?,?)',row)
                for port in (18104,18105,18106,18101,18102,18103,18080):control('start',port)
                run_checks(temp)
            except Exception:
                logs.flush();logs.seek(0);print(logs.read()[-6000:]);raise
            finally:
                for port in processes:control('stop',port)
                if USE_POSTGRES:
                    fixture_reservations=set(LEGACY_IDS)
                    if 'reservations' in POSTGRES_SERVICES:
                        with postgres.connect('reservations') as db:
                            for uid in FIXTURE_USERS | {LEGACY_USER}:
                                fixture_reservations.update(row['id'] for row in db.execute('SELECT id FROM reservations WHERE user_id=?',(uid,)).fetchall())
                            for rid in fixture_reservations:
                                db.execute('DELETE FROM outbox WHERE id IN (?,?)',('confirmed:'+rid,'cancelled:'+rid))
                                db.execute('DELETE FROM reservations WHERE id=? AND user_id IN ('+','.join('?' for _ in FIXTURE_USERS | {LEGACY_USER})+')',(rid,*sorted(FIXTURE_USERS | {LEGACY_USER})))
                    if 'availability' in POSTGRES_SERVICES:
                        with postgres.connect('availability') as db:
                            for rid in fixture_reservations | FIXTURE_ALLOCATION_IDS:
                                db.execute('DELETE FROM allocations WHERE reservation_id=?',(rid,))
                    # Ninguna consulta de limpieza usa correos o IDs ajenos a esta ejecución.
                    with postgres.connect('notifications') as db:
                        for uid in FIXTURE_USERS:
                            db.execute('DELETE FROM messages WHERE user_id=?',(uid,))
                    with postgres.connect('auth') as db:
                        for uid in FIXTURE_USERS:
                            db.execute('DELETE FROM outbox WHERE id=?',('welcome:'+uid,))
                            db.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
                            db.execute('DELETE FROM users WHERE id=?',(uid,))

if __name__=='__main__':main()
