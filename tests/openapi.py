"""Comprueba referencias y cobertura del contrato público e interno."""
from pathlib import Path
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]


class OpenAPI(unittest.TestCase):
    def test_recovery_contract_does_not_return_secrets(self):
        spec=yaml.safe_load((ROOT/'docs/openapi.yaml').read_text(encoding='utf-8'))
        forgot=spec['paths']['/auth/forgot-password']['post']
        reset=spec['paths']['/auth/reset-password']['post']
        self.assertIn('202',forgot['responses'])
        self.assertEqual(forgot['responses']['202']['content']['application/json']['schema'],{'$ref':'#/components/schemas/SecurityMessage'})
        fields=reset['requestBody']['content']['application/json']['schema']['properties']
        self.assertTrue(all(fields[key]['writeOnly'] for key in ('token','password','confirmPassword')))
        self.assertIn('attemptsRemaining',spec['components']['schemas']['Error']['properties'])

    def test_references_and_security(self):
        for name in ('openapi.yaml','internal-openapi.yaml'):
            spec=yaml.safe_load((ROOT/'docs'/name).read_text(encoding='utf-8'))
            self.assertEqual(spec['openapi'],'3.1.0')
            def walk(item):
                if isinstance(item,dict):
                    if '$ref' in item:
                        reference=item['$ref'];self.assertTrue(reference.startswith('#/'))
                        target=spec
                        for segment in reference[2:].split('/'):target=target[segment.replace('~1','/').replace('~0','~')]
                    if 'security' in item:
                        for scheme in item['security']:
                            for key in scheme:self.assertIn(key,spec['components']['securitySchemes'])
                    for value in item.values():walk(value)
                elif isinstance(item,list):
                    for value in item:walk(value)
            walk(spec)

    def test_administration_and_internal_routes(self):
        public=yaml.safe_load((ROOT/'docs/openapi.yaml').read_text(encoding='utf-8'))
        internal=yaml.safe_load((ROOT/'docs/internal-openapi.yaml').read_text(encoding='utf-8'))
        for path,method in (('/hotels','post'),('/hotels/{hotelId}','patch'),('/hotels/{hotelId}','delete'),('/rooms','post'),('/rooms/{roomId}','patch'),('/guests','get'),('/guests','post'),('/guests/{guestId}','patch'),('/inventory/{roomId}','put')):
            self.assertIn(method,public['paths'][path])
            self.assertTrue(public['paths'][path][method]['security'])
        for path in ('/internal/allocate','/internal/release','/internal/inventory','/internal/reconcile','/internal/events','/internal/users/{userId}','/health','/auth/me'):
            self.assertIn(path,internal['paths'])
        self.assertFalse(any(path.startswith('/internal/') for path in public['paths']))


if __name__=='__main__':unittest.main()
