"""Entrega por Gmail API HTTPS; los permisos OAuth se limitan a gmail.send."""
import base64
import json
import os
import threading
import time
import urllib.parse
import urllib.error
import urllib.request

TOKEN_URL = 'https://oauth2.googleapis.com/token'
SEND_URL = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
_token = ''
_expires = 0
_lock = threading.Lock()


def ready():
    return all(os.environ.get(key,'').strip() for key in ('GMAIL_CLIENT_ID','GMAIL_CLIENT_SECRET','GMAIL_REFRESH_TOKEN','SMTP_FROM'))


def access_token():
    global _token, _expires
    with _lock:
        if _token and time.time() < _expires:
            return _token
        payload=urllib.parse.urlencode({
            'grant_type':'refresh_token',
            'client_id':os.environ['GMAIL_CLIENT_ID'],
            'client_secret':os.environ['GMAIL_CLIENT_SECRET'],
            'refresh_token':os.environ['GMAIL_REFRESH_TOKEN']}).encode()
        request=urllib.request.Request(TOKEN_URL,data=payload,headers={'Content-Type':'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(request,timeout=12) as response:
            result=json.load(response)
        _token=result['access_token']
        _expires=time.time()+max(0,int(result.get('expires_in',3600))-60)
        return _token


def send(message):
    global _token, _expires
    # No se registran tokens, mensajes ni respuestas que puedan contener credenciales.
    raw=base64.urlsafe_b64encode(message.as_bytes()).decode()
    for attempt in range(2):
        request=urllib.request.Request(SEND_URL,data=json.dumps({'raw':raw}).encode(),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+access_token()})
        try:
            with urllib.request.urlopen(request,timeout=15) as response:
                result=json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 401 or attempt:
                raise
            with _lock:
                _token, _expires = '', 0
            continue
        if not result.get('id'):
            raise ValueError('Gmail no confirmó la aceptación del mensaje.')
        return
