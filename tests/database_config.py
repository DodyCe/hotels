"""Límites de configuración: separación física, TLS y credenciales por proceso."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'services'))
import postgres
from start import service_environment


class DatabaseConfiguration(unittest.TestCase):
    def test_same_database_is_rejected(self):
        direct = 'postgresql://postgres:example@db.projectone.supabase.co:5432/postgres'
        pooler = 'postgresql://postgres.projectone:example@aws-0-us-east-1.pooler.supabase.com:5432/postgres'
        with patch.dict(os.environ, AUTH_DATABASE_URL=direct, NOTIFICATIONS_DATABASE_URL=pooler):
            with self.assertRaisesRegex(ValueError, 'bases distintas'):
                postgres.validate_configuration(require_both=True)

    def test_distinct_projects_are_accepted(self):
        with patch.dict(os.environ,
            AUTH_DATABASE_URL='postgresql://postgres:example@db.projectone.supabase.co/postgres',
            NOTIFICATIONS_DATABASE_URL='postgresql://postgres:example@db.projecttwo.supabase.co/postgres'):
            postgres.validate_configuration(require_both=True)

    def test_both_connections_are_required_for_migration(self):
        with patch.dict(os.environ, AUTH_DATABASE_URL='', NOTIFICATIONS_DATABASE_URL=''):
            with self.assertRaisesRegex(ValueError, 'Completa'):
                postgres.validate_configuration(require_both=True)

    def test_invalid_connection_does_not_expose_password(self):
        with self.assertRaises(ValueError) as caught:
            postgres.connection_identity('https://postgres:PRIVATE-EXAMPLE@db.example.com/postgres')
        self.assertNotIn('PRIVATE-EXAMPLE', str(caught.exception))

    def test_remote_plaintext_is_rejected_before_connecting(self):
        with patch.dict(os.environ, AUTH_DATABASE_URL='postgresql://postgres:example@db.projectone.supabase.co/postgres?sslmode=disable'):
            with self.assertRaisesRegex(ValueError, 'TLS'):
                with postgres.connect('auth'):
                    self.fail('Nunca se debe abrir esta conexión')

    def test_only_owner_gets_database_and_smtp_credentials(self):
        with patch.dict(os.environ, AUTH_DATABASE_URL='auth-private', NOTIFICATIONS_DATABASE_URL='notifications-private',
                        CATALOG_DATABASE_URL='catalog-private', ROOMS_DATABASE_URL='rooms-private', SMTP_PASSWORD='smtp-private'):
            for path in ('services/auth.py', 'services/notifications.py', 'services/reservations.py',
                         'services/catalog.py', 'services/rooms.py', 'services/availability.py', 'gateway.py'):
                env = service_environment(path)
                self.assertEqual('AUTH_DATABASE_URL' in env, path == 'services/auth.py')
                self.assertEqual('NOTIFICATIONS_DATABASE_URL' in env, path == 'services/notifications.py')
                self.assertEqual('CATALOG_DATABASE_URL' in env, path == 'services/catalog.py')
                self.assertEqual('ROOMS_DATABASE_URL' in env, path == 'services/rooms.py')
                self.assertEqual('SMTP_PASSWORD' in env, path == 'services/notifications.py')

    def test_catalog_cannot_share_the_auth_project(self):
        with patch.dict(os.environ, AUTH_DATABASE_URL='postgresql://app:example@db.one.supabase.co/postgres',
                        CATALOG_DATABASE_URL='postgresql://other.one:example@aws-0-us-east-1.pooler.supabase.com/postgres'):
            with self.assertRaisesRegex(ValueError, 'bases distintas'):
                postgres.validate_configuration()

    def test_all_four_projects_must_be_present_when_required(self):
        with patch.dict(os.environ, CATALOG_DATABASE_URL='', ROOMS_DATABASE_URL=''):
            with self.assertRaisesRegex(ValueError, 'Completa'):
                postgres.validate_configuration(require_services=tuple(postgres.SETTINGS))

    def test_four_distinct_projects_are_accepted(self):
        settings = {key:f'postgresql://app:example@db.project{index}.supabase.co/postgres'
                    for index,key in enumerate(postgres.SETTINGS.values())}
        with patch.dict(os.environ, settings):
            postgres.validate_configuration(require_services=tuple(postgres.SETTINGS))


if __name__ == '__main__':
    unittest.main()
