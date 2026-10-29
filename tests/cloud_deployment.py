"""Configuración de nube y Gmail sin credenciales, correos ni bases reales."""
import base64
from email.message import EmailMessage
import http.client
from http.server import ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'services'),str(ROOT/'tools')]
import gmail_transport as gmail
from authorize_gmail import exchange, SCOPE
from start import service_environment


def response(data):
    result=io.BytesIO(json.dumps(data).encode())
    result.code=200
    result.headers=EmailMessage()
    return result


class GmailHTTPS(unittest.TestCase):
    def setUp(self):
        gmail._token,gmail._expires='',0
        self.env=patch.dict(os.environ,{'GMAIL_CLIENT_ID':'fixture-client','GMAIL_CLIENT_SECRET':'fixture-secret',
            'GMAIL_REFRESH_TOKEN':'fixture-refresh','SMTP_FROM':'fixture@example.test'},clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.message=EmailMessage()
        self.message['To']='recipient@example.test'
        self.message.set_content('Reserva de prueba sin envío real.')

    def test_mime_delivery_refresh_and_cache(self):
        with patch.object(gmail.urllib.request,'urlopen',side_effect=[response({'access_token':'fixture-token','expires_in':3600}),response({'id':'one'}),response({'id':'two'})]) as call:
            gmail.send(self.message); gmail.send(self.message)
        self.assertEqual(call.call_count,3)
        token_request=call.call_args_list[0].args[0]
        self.assertEqual(token_request.full_url,gmail.TOKEN_URL)
        self.assertIn(b'grant_type=refresh_token',token_request.data)
        send_request=call.call_args_list[1].args[0]
        self.assertEqual(send_request.full_url,gmail.SEND_URL)
        self.assertEqual(send_request.get_header('Authorization'),'Bearer fixture-token')
        raw=json.loads(send_request.data)['raw']
        self.assertEqual(base64.urlsafe_b64decode(raw),self.message.as_bytes())

    def test_unauthorized_refreshes_once(self):
        denied=urllib.error.HTTPError(gmail.SEND_URL,401,'unauthorized',{},None)
        values=[response({'access_token':'first'}),denied,response({'access_token':'second'}),response({'id':'sent'})]
        with patch.object(gmail.urllib.request,'urlopen',side_effect=values) as call:
            gmail.send(self.message)
        self.assertEqual(call.call_count,4)
        self.assertEqual(call.call_args_list[-1].args[0].get_header('Authorization'),'Bearer second')

    def test_ambiguous_failure_is_not_immediately_resent(self):
        with patch.object(gmail.urllib.request,'urlopen',side_effect=[response({'access_token':'first'}),TimeoutError()]) as call:
            with self.assertRaises(TimeoutError): gmail.send(self.message)
        self.assertEqual(call.call_count,2)

    def test_missing_acceptance_is_failure(self):
        with patch.object(gmail.urllib.request,'urlopen',side_effect=[response({'access_token':'first'}),response({})]):
            with self.assertRaises(ValueError): gmail.send(self.message)

    def test_oauth_scope_is_send_only(self):
        client={'client_id':'fixture','client_secret':'fixture-secret'}
        for scope in (SCOPE+' https://mail.google.com/','https://mail.google.com/'):
            with patch('authorize_gmail.urllib.request.urlopen',return_value=response({'refresh_token':'fixture','scope':scope})):
                with self.assertRaises(ValueError): exchange(client,'code','http://127.0.0.1:1/oauth/callback','verifier')
        with patch('authorize_gmail.urllib.request.urlopen',return_value=response({'refresh_token':'fixture','scope':SCOPE})):
            result=exchange(client,'code','http://127.0.0.1:1/oauth/callback','verifier')
        self.assertEqual(set(result),{'GMAIL_CLIENT_ID','GMAIL_CLIENT_SECRET','GMAIL_REFRESH_TOKEN'})

    def test_only_notifications_receives_oauth(self):
        with patch.dict(os.environ,ORIGIN_SECRET='fixture-origin-secret'):
            for path in ('gateway.py',*('services/'+name+'.py' for name in ('auth','notifications','catalog','rooms','reservations','availability'))):
                env=service_environment(path)
                self.assertEqual('GMAIL_REFRESH_TOKEN' in env,path=='services/notifications.py')
                self.assertEqual('ORIGIN_SECRET' in env,path=='gateway.py')


class CloudConfiguration(unittest.TestCase):
    def test_blueprint_database_isolation_and_free_plan(self):
        config=yaml.safe_load((ROOT/'render.yaml').read_text(encoding='utf-8'))
        self.assertEqual(len(config['services']),7)
        for service in config['services']:
            self.assertEqual(service['plan'],'free')
            self.assertEqual(service['runtime'],'docker')
            self.assertEqual(service['autoDeployTrigger'],'checksPass')
            env={item.get('key'):item for item in service['envVars']}
            owned=service['name'].removeprefix('hotels-')
            dbkeys=[key for key in env if key and key.endswith('_DATABASE_URL')]
            self.assertEqual(dbkeys,[] if owned=='gateway' else [owned.upper()+'_DATABASE_URL'])
            self.assertEqual('GMAIL_REFRESH_TOKEN' in env,owned=='notifications')
            self.assertFalse(any(path.startswith('web') for path in service['buildFilter']['paths']))
            for item in env.values():
                if 'fromService' in item:
                    self.assertEqual(item['fromService']['envVarKey'],'RENDER_EXTERNAL_URL')

    def test_render_never_falls_back_to_ephemeral_sqlite(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'INTERNAL_API_KEY':'x'*48,'HOTELS_DATA_DIR':directory},clear=True):
            import common
            with patch.dict(os.environ,RENDER='true'):
                with self.assertRaises(RuntimeError):
                    with common.connect('auth'): self.fail('No debe crear SQLite en Render.')


class GatewayBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env=patch.dict(os.environ,{'INTERNAL_API_KEY':'x'*48,'ORIGIN_SECRET':'s'*48,'GATEWAY_API_ONLY':'1','PUBLIC_ORIGIN':'https://hotels.example.test'},clear=True)
        cls.env.start()
        import gateway
        cls.gateway=gateway
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),gateway.Gateway)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(); cls.env.stop()

    def request(self,path,headers=None,method='GET'):
        connection=http.client.HTTPConnection(*self.server.server_address,timeout=5)
        connection.request(method,path,headers={'Host':'127.0.0.1:8080',**(headers or {})})
        result=connection.getresponse()
        body=result.read()
        status=result.status
        connection.close()
        return status,body

    def test_gateway_rejects_direct_requests_but_health_is_public(self):
        self.assertEqual(self.request('/api/auth/me')[0],403)
        self.assertEqual(self.request('/api/readiness')[0],403)
        self.assertEqual(self.request('/health')[0],200)
        self.assertEqual(self.request('/')[0],404)

    def test_trusted_proxy_ip_forwarded_without_exposing_origin_secret(self):
        with patch.object(self.gateway.urllib.request,'urlopen',return_value=response({'user':{}})) as call:
            status,_=self.request('/api/auth/me',{'X-Origin-Secret':'s'*48,'X-Real-IP':'203.0.113.7','Cookie':'hotels_session=fixture'})
        self.assertEqual(status,200)
        upstream=call.call_args.args[0]
        self.assertEqual(upstream.get_header('X-client-ip'),'203.0.113.7')
        self.assertEqual(upstream.get_header('Cookie'),'hotels_session=fixture')
        self.assertIsNone(upstream.get_header('X-origin-secret'))

    def test_readiness_reports_failed_dependency(self):
        def health(request,**_):
            if ':8105/' in request: raise OSError('offline')
            return response({'status':'ok'})
        with patch.object(self.gateway.urllib.request,'urlopen',side_effect=health):
            status,body=self.request('/api/readiness',{'X-Origin-Secret':'s'*48})
        self.assertEqual(status,200)
        self.assertFalse(json.loads(body)['ready'])
        self.assertFalse(json.loads(body)['services']['rooms'])

    def test_render_rejects_cross_origin_posts(self):
        with patch.dict(os.environ,RENDER='true'):
            status,_=self.request('/api/auth/login',{'X-Origin-Secret':'s'*48,'Origin':'https://foreign.example.test'},method='POST')
        self.assertEqual(status,403)


if __name__=='__main__': unittest.main()
