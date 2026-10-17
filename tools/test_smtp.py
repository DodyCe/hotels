"""Verifica configuración y, con --send, envía un único correo de comprobación."""
import argparse
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from start import load_environment

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--send',action='store_true',help='Envía un mensaje al SMTP_TEST_TO configurado en .env')
    options = parser.parse_args()
    load_environment()
    required = ['SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','SMTP_FROM','SMTP_TEST_TO']
    missing = [key for key in required if not os.environ.get(key,'').strip()]
    if missing:
        print('Completa estos campos en .env: '+', '.join(missing))
        return 1
    if not options.send:
        print('Configuración completa. No se ha enviado ningún mensaje. Para enviarlo: python tools/test_smtp.py --send')
        return 0
    message = EmailMessage()
    message['From'] = os.environ['SMTP_FROM']
    message['To'] = os.environ['SMTP_TEST_TO']
    message['Subject'] = 'Hotels — comprobación de correo'
    message.set_content('Este es un único mensaje de prueba de Hotels.\nEste mensaje comprueba la configuración del servicio de notificaciones.\nSi lo recibes, confirma la llegada en tu bandeja de entrada o spam.\n')
    try:
        mode = os.environ.get('SMTP_SECURITY','starttls').lower()
        context = ssl.create_default_context()
        if mode == 'ssl':
            client = smtplib.SMTP_SSL(os.environ['SMTP_HOST'],int(os.environ['SMTP_PORT']),timeout=15,context=context)
        elif mode == 'starttls':
            client = smtplib.SMTP(os.environ['SMTP_HOST'],int(os.environ['SMTP_PORT']),timeout=15)
        else:
            raise ValueError('SMTP_SECURITY inválido')
        with client:
            if mode == 'starttls':
                client.ehlo(); client.starttls(context=context); client.ehlo()
            client.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
            client.send_message(message)
    except smtplib.SMTPResponseException as error:
        print(f'El proveedor rechazó la prueba: SMTP {error.smtp_code}. Revisa la cuenta y la contraseña de aplicación.')
        return 1
    except Exception as error:
        print('No se pudo completar la conexión SMTP: '+type(error).__name__+'. No se muestran credenciales.')
        return 1
    print('El servidor SMTP aceptó el correo de prueba. Revisa la bandeja de destino y spam para comprobar la llegada.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
