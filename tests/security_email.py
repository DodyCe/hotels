"""Valida entrega TLS, caducidad y eliminación del enlace sin enviar correo real."""
import os
from pathlib import Path
import ssl
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

DIRECTORY = tempfile.TemporaryDirectory(prefix='hotels-security-email-')
os.environ.update(INTERNAL_API_KEY='security-email-fixture-key-'+'x'*32,HOTELS_DATA_DIR=DIRECTORY.name,
                  PUBLIC_ORIGIN='http://127.0.0.1:8080',NOTIFICATIONS_DATABASE_URL='')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services'))
import notifications
from common import APIError, connect


class SecurityEmail(unittest.TestCase):
    def setUp(self):
        with connect('notifications') as db:
            db.execute('DELETE FROM messages')

    def queue(self,age=0):
        token='a'*43
        user={'id':'fixture','name':'Huésped','email':'fixture@example.test'}
        subject,body=notifications.compose('password.reset',{'resetUrl':'http://127.0.0.1:8080/reset-password.html#token='+token},user)
        with connect('notifications') as db:
            db.execute('INSERT INTO messages(id,user_id,recipient,subject,body,status,created) VALUES (?,?,?,?,?,?,?)',
                       ('password-reset:fixture',user['id'],user['email'],subject,body,'pendiente',time.time()-age))
        return token

    def run_worker(self):
        with patch.dict(os.environ,{'SMTP_HOST':'smtp.example.test','SMTP_USER':'fixture','SMTP_PASSWORD':'fixture-password','SMTP_FROM':'fixture@example.test','SMTP_SECURITY':'starttls','SMTP_PORT':'587'}):
            with patch('notifications.smtplib.SMTP') as smtp, patch('notifications.time.sleep',side_effect=StopIteration):
                with self.assertRaises(StopIteration):
                    notifications.smtp_worker()
                return smtp

    def test_send_uses_tls_then_removes_private_link(self):
        token=self.queue()
        smtp=self.run_worker()
        client=smtp.return_value
        context=client.starttls.call_args.kwargs['context']
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        message=client.send_message.call_args.args[0]
        self.assertEqual(message['To'],'fixture@example.test')
        self.assertIn('#token='+token,message.get_content())
        with connect('notifications') as db:
            row=db.execute('SELECT status,body FROM messages').fetchone()
        self.assertEqual(row['status'],'aceptado_smtp')
        self.assertNotIn(token,row['body'])

    def test_expired_link_is_not_sent(self):
        token=self.queue(age=901)
        smtp=self.run_worker()
        smtp.assert_not_called()
        with connect('notifications') as db:
            row=db.execute('SELECT status,body FROM messages').fetchone()
        self.assertEqual(row['status'],'caducado')
        self.assertNotIn(token,row['body'])

    def test_email_rejects_a_different_reset_destination(self):
        with self.assertRaises(APIError):
            notifications.compose('password.reset',{'resetUrl':'https://other.example.test/reset-password.html#token='+'a'*43},
                                  {'name':'Huésped','email':'fixture@example.test'})


if __name__=='__main__':
    try:
        unittest.main()
    finally:
        DIRECTORY.cleanup()
