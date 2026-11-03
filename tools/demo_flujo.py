"""Recorre el flujo de negocio completo por el Gateway y muestra cada paso.

Uso, con Hotels iniciado:  python tools/demo_flujo.py [http://127.0.0.1:8080]
Crea una cuenta nueva @example.test, reserva, cancela y lista los avisos.
"""
import datetime as dt
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8080').rstrip('/')
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json'} if data else {})
    try:
        response = opener.open(request, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.code, json.load(response)

def step(number, title, method, path, body=None):
    code, data = call(method, path, body)
    print(f'\n{number}. {title}\n   {method} {path} -> HTTP {code}')
    return code, data

today = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).date()
checkin, checkout = today + dt.timedelta(days=30), today + dt.timedelta(days=33)
email = f'demo-{int(time.time())}@example.test'

code, data = step(1, 'Estado de los microservicios', 'GET', '/api/readiness')
for name, ready in data['services'].items():
    print(f"   - {name}: {'activo' if ready else 'sin respuesta'}")

code, data = step(2, 'Registro e inicio de sesión (Auth)', 'POST', '/api/auth/register',
                  {'name': 'Usuario Demo', 'email': email, 'password': 'Demo-Hotels-2026'})
print(f"   Usuario {data['user']['id']} con cookie de sesión HttpOnly")

code, data = step(3, 'Consultar hoteles (Catálogo)', 'GET', '/api/hotels')
print('   ' + ', '.join(h['name'] for h in data['hotels']))

code, data = step(4, 'Consultar habitaciones para 2 huéspedes (Habitaciones)', 'GET', '/api/rooms?hotelId=ghl-monteria&guests=2')
room = data['rooms'][0]
print(f"   {room['id']}: {room['name']}, {room['price']} COP por noche")

query = f'checkin={checkin}&checkout={checkout}'
code, data = step(5, f'Consultar disponibilidad {checkin} a {checkout} (Inventario)', 'GET', '/api/availability?' + query)
before = next(a['available'] for a in data['availability'] if a['roomId'] == room['id'])
print(f'   Unidades libres de {room["id"]}: {before}')

code, data = step(6, 'Crear la reserva (Reservas -> Habitaciones, Catálogo, Inventario)', 'POST', '/api/reservations',
                  {'roomId': room['id'], 'checkin': str(checkin), 'checkout': str(checkout), 'guests': 2})
reservation = data['reservation']
print(f"   {reservation['id']}: {reservation['status']}, total {reservation['total']} COP calculado por el servidor")

code, data = step(7, 'Inventario actualizado', 'GET', '/api/availability?' + query)
after = next(a['available'] for a in data['availability'] if a['roomId'] == room['id'])
print(f'   Unidades libres de {room["id"]}: {before} -> {after}')

time.sleep(2)
code, data = step(8, 'Avisos generados (Notificaciones, vía outbox)', 'GET', '/api/notifications')
for message in data['notifications']:
    print(f"   - {message['subject']} [{message['status']}]")

code, data = step(9, 'Cancelar la reserva', 'POST', f"/api/reservations/{reservation['id']}/cancel", {})
print(f"   Estado: {data['status']}")

code, data = step(10, 'Inventario liberado', 'GET', '/api/availability?' + query)
print(f'   Unidades libres de {room["id"]}: ' + str(next(a['available'] for a in data['availability'] if a['roomId'] == room['id'])))

time.sleep(2)
code, data = step(11, 'Aviso de cancelación', 'GET', '/api/notifications')
for message in data['notifications']:
    print(f"   - {message['subject']} [{message['status']}]")

code, data = step(12, 'Cerrar sesión', 'POST', '/api/auth/logout', {})
print(f"   Consultar reservas sin sesión -> HTTP {call('GET', '/api/reservations')[0]}")
