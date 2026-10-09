"""Tests : lecture automatique des photos (vision.py et /api/contributions/scan). Aucun appel réseau réel.
Lancer : python -m unittest test_vision -v"""
import io
import json
import os
import unittest
import unittest.mock
import urllib.error

import vision
from test_collaboration import CollabCase


class FakeResponse:
    def __init__(self, text):
        self.body = json.dumps({'content': [{'type': 'text', 'text': text}]}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def opener_returning(text, seen=None):
    def opener(request, timeout=None):
        if seen is not None:
            seen.append((request, timeout))
        return FakeResponse(text)
    return opener


class VisionCase(unittest.TestCase):
    def setUp(self):
        patcher = unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_VISION_API_KEY': 'cle-de-test'})
        patcher.start()
        self.addCleanup(patcher.stop)
        vision._usage.update(day=None, count=0)


class TestCleanFields(unittest.TestCase):
    def test_valid_values_are_kept(self):
        out = vision.clean_fields({'article': ' Riz  parfumé ', 'brand': 'Maman', 'quantity': 5, 'unit': 'kg', 'price': 3500})
        self.assertEqual(out, {'article': 'Riz parfumé', 'brand': 'Maman', 'quantity': 5.0, 'unit': 'kg', 'price': 3500})

    def test_doubtful_values_are_dropped_never_invented(self):
        out = vision.clean_fields({'article': '', 'brand': 12, 'quantity': -3, 'unit': 'tonne', 'price': 12.5})
        self.assertEqual(out, {})
        self.assertEqual(vision.clean_fields({'price': True, 'quantity': True}), {})
        self.assertEqual(vision.clean_fields({'price': 10**9}), {})
        self.assertEqual(vision.clean_fields('pas un objet'), {})

    def test_unknown_keys_are_ignored_and_text_is_bounded(self):
        out = vision.clean_fields({'article': 'x' * 500, 'admin': 'true'})
        self.assertEqual(list(out), ['article'])
        self.assertEqual(len(out['article']), 200)


class TestExtract(VisionCase):
    def test_parses_json_even_when_wrapped_in_text(self):
        seen = []
        out = vision.extract(b'jpeg', opener_returning('Voici : {"article":"Huile","quantity":1,"unit":"L","price":1800} merci', seen))
        self.assertEqual(out, {'article': 'Huile', 'quantity': 1.0, 'unit': 'L', 'price': 1800})
        request, timeout = seen[0]
        self.assertEqual(request.get_header('X-api-key'), 'cle-de-test')
        self.assertEqual(timeout, 25)
        sent = json.loads(request.data)
        self.assertEqual(sent['model'], 'claude-haiku-5-5')
        self.assertEqual(sent['messages'][0]['content'][0]['source']['media_type'], 'image/jpeg')

    def test_unusable_answers_give_empty_dict(self):
        for text in ('je ne sais pas', '{pas du json}', ''):
            self.assertEqual(vision.extract(b'x', opener_returning(text)), {}, text)

    def test_network_failures_become_a_safe_message(self):
        for failure in (urllib.error.URLError('dns'), TimeoutError(), urllib.error.HTTPError('u', 401, 'Unauthorized', {}, None)):
            def opener(request, timeout=None, failure=failure):
                raise failure
            with self.assertRaises(vision.VisionError) as ctx:
                vision.extract(b'x', opener)
            self.assertNotIn('cle-de-test', str(ctx.exception))
            self.assertNotIn('401', str(ctx.exception))

    def test_disabled_without_key(self):
        with unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_VISION_API_KEY': ''}):
            self.assertFalse(vision.configured())
            with self.assertRaises(vision.VisionError):
                vision.extract(b'x', opener_returning('{}'))

    def test_daily_cap_stops_calls(self):
        with unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_VISION_DAILY_MAX': '2'}):
            vision.extract(b'x', opener_returning('{}'))
            vision.extract(b'x', opener_returning('{}'))
            with self.assertRaises(vision.VisionError):
                vision.extract(b'x', opener_returning('{}'))


class TestScanRoute(VisionCase, CollabCase):
    def setUp(self):
        VisionCase.setUp(self)
        CollabCase.setUp(self)

    def png(self, size=(300, 200)):
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', size, (10, 120, 10)).save(buf, 'PNG')
        buf.seek(0)
        return buf

    def scan(self, **kw):
        data = {'photo': (kw.get('photo') or self.png(), 'p.png')}
        return self.client.post('/api/contributions/scan', data=data, headers=kw.get('headers', self.csrf()))

    def fake_extract(self, fields=None):
        return unittest.mock.patch('vision.extract', return_value=fields or {'article': 'Riz', 'price': 3000})

    def test_requires_login_and_csrf(self):
        self.assertEqual(self.scan().status_code, 401)
        self.register()
        self.assertEqual(self.scan(headers={}).status_code, 403)

    def test_returns_proposed_fields_and_stores_nothing(self):
        self.register()
        with self.fake_extract() as extract:
            r = self.scan()
        self.assertEqual((r.status_code, r.get_json()['fields']), (200, {'article': 'Riz', 'price': 3000}))
        sent = extract.call_args.args[0]
        self.assertTrue(sent.startswith(b'\xff\xd8'))  # JPEG réencodé, sans métadonnées
        self.assertFalse(os.path.exists(os.path.join(os.environ['COMPAREPRIX_DATA_DIR'], 'proofs')))
        self.assertEqual(self.client.get('/api/contributions').get_json()['contributions'], [])

    def test_disabled_gives_503_and_session_flag_follows_configuration(self):
        self.register()
        self.assertTrue(self.client.get('/api/session').get_json()['features']['photo_scan'])
        with unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_VISION_API_KEY': ''}):
            self.assertFalse(self.client.get('/api/session').get_json()['features']['photo_scan'])
            self.assertEqual(self.scan().status_code, 503)

    def test_invalid_photo_and_missing_photo_are_refused_before_any_call(self):
        self.register()
        with self.fake_extract() as extract:
            bad = self.client.post('/api/contributions/scan', data={'photo': (io.BytesIO(b'pas une image'), 'p.png')}, headers=self.csrf())
            none = self.client.post('/api/contributions/scan', data={}, headers=self.csrf())
        self.assertEqual((bad.status_code, none.status_code), (400, 400))
        extract.assert_not_called()

    def test_nothing_readable_gives_422_and_provider_failure_gives_503(self):
        self.register()
        with self.fake_extract({}) as extract:
            extract.return_value = {}
            self.assertEqual(self.scan().status_code, 422)
        with unittest.mock.patch('vision.extract', side_effect=vision.VisionError('indispo')):
            r = self.scan()
        self.assertEqual((r.status_code, r.get_json()['message']), (503, 'indispo'))

    def test_per_user_hourly_limit(self):
        self.register()
        with self.fake_extract():
            codes = [self.scan().status_code for _ in range(11)]
        self.assertEqual(codes, [200] * 10 + [429])


if __name__ == '__main__':
    unittest.main()
