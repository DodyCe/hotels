"""Autoriza gmail.send mediante OAuth de escritorio; guarda el resultado solo en data/."""
import argparse
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import time
import urllib.parse
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'https://www.googleapis.com/auth/gmail.send'


def exchange(client, code, redirect, verifier):
    payload=urllib.parse.urlencode({'code':code,'client_id':client['client_id'],
        'client_secret':client['client_secret'],'redirect_uri':redirect,
        'grant_type':'authorization_code','code_verifier':verifier}).encode()
    request=urllib.request.Request('https://oauth2.googleapis.com/token',data=payload,
        headers={'Content-Type':'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(request,timeout=15) as response:
        result=json.load(response)
    if not result.get('refresh_token') or set(result.get('scope',SCOPE).split()) != {SCOPE}:
        raise ValueError('Google no entregó un permiso persistente exclusivo de envío.')
    return {'GMAIL_CLIENT_ID':client['client_id'],'GMAIL_CLIENT_SECRET':client['client_secret'],
            'GMAIL_REFRESH_TOKEN':result['refresh_token']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',required=True,help='JSON privado de un cliente OAuth de escritorio de Google.')
    parser.add_argument('--sender',required=True,help='Cuenta de Gmail que autorizará el envío.')
    parser.add_argument('--output',default=str(ROOT/'data/provisioning/gmail-render.json'))
    args=parser.parse_args()
    output=Path(args.output).resolve()
    if not output.is_relative_to((ROOT/'data').resolve()) or output.exists():
        parser.error('La salida debe ser un archivo nuevo dentro de data/ (ignorado por Git).')
    client=json.loads(Path(args.client).read_text(encoding='utf-8')).get('installed')
    if not client or not client.get('client_id') or not client.get('client_secret'):
        parser.error('Se requiere un cliente OAuth de tipo Aplicación de escritorio.')
    state=secrets.token_urlsafe(32)
    verifier=secrets.token_urlsafe(48)
    result={}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self,*_):
            pass  # Nunca registrar el código OAuth de la URL.

        def do_GET(self):
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            valid=(urllib.parse.urlsplit(self.path).path=='/oauth/callback'
                   and hmac.compare_digest(query.get('state',[''])[0],state))
            if not valid:
                self.send_error(400); return
            if query.get('code') and not result:
                result['code']=query['code'][0]
            elif query.get('error'):
                result['error']=True
            self.send_response(200)
            self.send_header('Content-Type','text/plain; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','no-referrer')
            self.end_headers()
            self.wfile.write('Solicitud recibida. Puedes cerrar esta pestaña.'.encode())

    with HTTPServer(('127.0.0.1',0),Callback) as server:
        server.timeout=1
        redirect=f'http://127.0.0.1:{server.server_port}/oauth/callback'
        query=urllib.parse.urlencode({'client_id':client['client_id'],'redirect_uri':redirect,
            'response_type':'code','scope':SCOPE,'access_type':'offline','prompt':'consent',
            'state':state,'login_hint':args.sender,'code_challenge_method':'S256',
            'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')})
        webbrowser.open('https://accounts.google.com/o/oauth2/v2/auth?'+query)
        print('Autoriza solo el envío con la cuenta dedicada en el navegador. Tiempo máximo: 10 minutos.',flush=True)
        deadline=time.monotonic()+600
        while not result and time.monotonic()<deadline:
            server.handle_request()
        if not result.get('code'):
            raise SystemExit('Autorización cancelada o vencida; no se guardaron credenciales.')
        try:
            config=exchange(client,result['code'],redirect,verifier)
        except Exception:
            raise SystemExit('Google no completó el intercambio; no se guardaron credenciales.') from None
    config['SMTP_FROM']=args.sender
    config['MAIL_PROVIDER']='gmail_api'
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as file:
        json.dump(config,file,indent=2)
    print('Credenciales guardadas en el archivo privado indicado; no se muestran ni se suben a Git.')


if __name__=='__main__':
    main()
