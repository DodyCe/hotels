"""Notificaciones: resuelve destinatarios en Auth y entrega por SMTP configurable."""
import hashlib
import logging
import os
import smtplib
import ssl
import threading
import time
import postgres
import re
from account_security import RESET_SECONDS, recovery_origin
from email.message import EmailMessage
from common import APIError, AUTH, Handler, connect, internal_request, serve, user_for

with connect('notifications') as db:
    if postgres.database_url('notifications'):
        postgres.initialize('notifications', db)
    else:
        db.execute('''CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, recipient TEXT NOT NULL,
            subject TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL,
            created DOUBLE PRECISION NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_try DOUBLE PRECISION NOT NULL DEFAULT 0)''')

def smtp_ready():
    return all(os.environ.get(key, '').strip() for key in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM'))

def compose(kind, payload, user):
    greeting = 'Hola, ' + user['name'] + '.\n\n'
    if kind == 'welcome':
        subject = 'Bienvenido a Hotels'
        content = 'Tu cuenta fue creada. Ya puedes consultar, registrar y cancelar tus reservas.'
    elif kind == 'password.reset':
        url = payload.get('resetUrl','')
        if not isinstance(url,str) or not re.fullmatch(re.escape(recovery_origin()+'/reset-password.html#token=')+r'[A-Za-z0-9_-]{43}',url):
            raise APIError(400, 'Enlace de recuperación inválido.')
        subject = 'Restablece tu contraseña de Hotels'
        content = ('Recibimos una solicitud para restablecer tu contraseña.\n\n'
                   'Abre este enlace para elegir una nueva contraseña:\n'+url+
                   '\n\nEl enlace vence en 15 minutos y solo se puede usar una vez. '
                   'Si solicitaste varios enlaces, usa el último. '
                   'Si no solicitaste este cambio, ignora este correo. Tu contraseña sigue siendo la misma.')
    elif kind == 'password.changed':
        subject = 'Tu contraseña de Hotels fue actualizada'
        content = ('Tu contraseña se actualizó y se cerraron todas tus sesiones anteriores. '
                   'Si no reconoces este cambio, solicita la recuperación de tu cuenta desde Hotels.')
    elif kind in ('reservation.confirmed', 'reservation.cancelled'):
        cancelled = kind.endswith('cancelled')
        subject = ('Cancelación' if cancelled else 'Confirmación') + ' de reserva ' + str(payload.get('id', ''))
        content = (f"Reserva: {payload.get('id', '')}\nHotel: {payload.get('hotel', '')}\n"
                   f"Habitación: {payload.get('room', '')}\nLlegada: {payload.get('checkin', '')}\nSalida: {payload.get('checkout', '')}\n"
                   f"Huéspedes: {payload.get('guests', '')}\nTotal: {payload.get('total', '')} COP\n"
                   f"Estado: {'Cancelada' if cancelled else 'Confirmada'}")
    else:
        raise APIError(400, 'Tipo de notificación no permitido.')
    footer = ('\n\nHOTELS · GESTIÓN DE RESERVAS\nHotels es un proyecto académico independiente. '
              'No constituye una reserva real, un cobro ni un comprobante del hotel. '
              'Hotels no representa ni tiene afiliación con los establecimientos mencionados.\n')
    return subject, greeting + content + footer

class Notifications(Handler):
    service_name = 'notificaciones'
    database_name = 'notifications'
    def route(self):
        if self.command == 'GET' and self.path == '/notifications':
            user = user_for(self)
            with connect('notifications') as db:
                rows = db.execute('SELECT id,recipient,subject,body,status,created FROM messages WHERE user_id=? AND id NOT LIKE ? ORDER BY created DESC LIMIT 100', (user['id'],'password-reset:%')).fetchall()
            return self.respond(200, {'notifications': [dict(r) for r in rows], 'smtpConfigured': smtp_ready()})
        if self.command == 'POST' and self.path == '/internal/events':
            event = self.body()
            if not isinstance(event.get('id'), str) or not 1 <= len(event['id']) <= 160 or not isinstance(event.get('userId'), str) or not isinstance(event.get('payload'), dict):
                raise APIError(400, 'Evento inválido.')
            private_reset = event.get('kind') == 'password.reset'
            if private_reset != event['id'].startswith('password-reset:'):
                raise APIError(400, 'Identificador de recuperación inválido.')
            created = time.time()
            if private_reset:
                expires = event['payload'].get('expiresAt')
                if not isinstance(expires,(int,float)) or isinstance(expires,bool) or not 0 < expires <= time.time()+RESET_SECONDS+5:
                    raise APIError(400, 'Vencimiento de recuperación inválido.')
                if expires <= time.time():
                    return self.respond(200, {'accepted':True,'expired':True})
                created = expires-RESET_SECONDS
            with connect('notifications') as db:
                existing = db.execute('SELECT id FROM messages WHERE id=?', (event['id'],)).fetchone()
            if existing:
                return self.respond(200, {'accepted': True, 'duplicate': True})
            # El correo se consulta en Auth; ningún formulario elige destinatarios ajenos.
            user = internal_request(AUTH, '/internal/users/' + event['userId'])['user']
            subject, content = compose(event.get('kind'), event['payload'], user)
            status = 'pendiente' if smtp_ready() else 'vista_previa'
            with connect('notifications') as db:
                db.execute('INSERT INTO messages(id,user_id,recipient,subject,body,status,created) VALUES (?,?,?,?,?,?,?) ON CONFLICT (id) DO NOTHING', (event['id'], user['id'], user['email'], subject, content, status, created))
            return self.respond(202, {'accepted': True})
        raise APIError(404, 'Ruta no encontrada.')

def smtp_worker():
    host = os.environ.get('SMTP_HOST', '').strip()
    if not smtp_ready():
        return
    while True:
        try:
            with connect('notifications') as db:
                rows = db.execute("SELECT * FROM messages WHERE status IN ('pendiente','reintentando') AND attempts<5 AND next_try<=? ORDER BY created LIMIT 10", (time.time(),)).fetchall()
            for row in rows:
                private_reset = row['id'].startswith('password-reset:')
                if private_reset and row['created']+RESET_SECONDS <= time.time():
                    with connect('notifications') as db:
                        db.execute("UPDATE messages SET status='caducado',body='El enlace de recuperación venció.' WHERE id=?", (row['id'],))
                    continue
                try:
                    sender = os.environ.get('SMTP_FROM', '').strip()
                    if not sender or '\n' in sender or '\r' in sender:
                        raise ValueError('SMTP_FROM requerido')
                    message = EmailMessage()
                    message['From'], message['To'], message['Subject'] = sender, row['recipient'], row['subject']
                    message['Message-ID'] = '<' + hashlib.sha256(row['id'].encode()).hexdigest() + '@hotels.local>'
                    message.set_content(row['body'])
                    mode = os.environ.get('SMTP_SECURITY', 'starttls').lower()
                    if mode not in ('ssl', 'starttls'):
                        raise ValueError('SMTP_SECURITY debe ser ssl o starttls')
                    context = ssl.create_default_context()
                    port = int(os.environ.get('SMTP_PORT', '465' if mode == 'ssl' else '587'))
                    client = smtplib.SMTP_SSL(host, port, timeout=12, context=context) if mode == 'ssl' else smtplib.SMTP(host, port, timeout=12)
                    with client:
                        if mode == 'starttls':
                            client.ehlo(); client.starttls(context=context); client.ehlo()
                        if os.environ.get('SMTP_USER'):
                            client.login(os.environ['SMTP_USER'], os.environ.get('SMTP_PASSWORD', ''))
                        client.send_message(message)
                    with connect('notifications') as db:
                        db.execute("UPDATE messages SET status='aceptado_smtp',attempts=attempts+1 WHERE id=?", (row['id'],))
                        if private_reset:
                            db.execute("UPDATE messages SET body='Se envió un enlace de recuperación por correo.' WHERE id=?", (row['id'],))
                except Exception:
                    # SMTP aceptado no prueba entrega a la bandeja de entrada.
                    with connect('notifications') as db:
                        db.execute('UPDATE messages SET status=?,attempts=attempts+1,next_try=? WHERE id=?', ('error' if row['attempts'] >= 4 else 'reintentando', time.time()+min(300, 15*(2**row['attempts'])), row['id']))
                    logging.warning('Entrega SMTP fallida; revisar configuración del proveedor (evento %s)', row['id'])
        except Exception:
            logging.exception('Error procesando la cola SMTP')
        time.sleep(2)

if __name__ == '__main__':
    threading.Thread(target=smtp_worker, daemon=True).start()
    serve(Notifications, 8102)
