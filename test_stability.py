"""Tests : sonde /healthz (bases + espace disque), pages d'erreur, réduction des photos, purge des tables temporaires.
Lancer : python -m unittest test_stability -v"""
import atexit
import io
import os
import sqlite3
import tempfile
import unittest
import unittest.mock
from collections import namedtuple

_TMP = tempfile.TemporaryDirectory()
atexit.register(_TMP.cleanup)
os.environ.setdefault('COMPAREPRIX_DB', os.path.join(_TMP.name, 'c.db'))

import db
import app as appmod
from test_collaboration import CollabCase, PHONE

Usage = namedtuple('Usage', 'total used free')


class TestHealthz(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        patcher = unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_DB': os.path.join(tmp.name, 'c.db'),
                                                         'COMPAREPRIX_DATA_DIR': tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        db.init_db(seed=False)
        self.client = appmod.app.test_client()

    def test_ok_when_everything_is_fine(self):
        r = self.client.get('/healthz')
        self.assertEqual((r.status_code, r.get_json()), (200, {'status': 'ok'}))

    def test_low_disk_gives_503_with_reason(self):
        with unittest.mock.patch('shutil.disk_usage', return_value=Usage(10**9, 10**9 - 10**6, 10**6)):
            r = self.client.get('/healthz')
        self.assertEqual((r.status_code, r.get_json()), (503, {'status': 'error', 'reason': 'disque'}))

    def test_quota_threshold_is_90_percent_and_off_by_default(self):
        with open(os.path.join(self.dir, 'gros.bin'), 'wb') as f:
            f.write(b'0' * 2_000_000)
        with unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_QUOTA_MB': '2'}):
            self.assertEqual(self.client.get('/healthz').get_json().get('reason'), 'quota')
        with unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_QUOTA_MB': '1000'}):
            self.assertEqual(self.client.get('/healthz').status_code, 200)
        self.assertEqual(self.client.get('/healthz').status_code, 200)

    def test_corrupt_community_database_gives_503_without_detail(self):
        with open(os.path.join(self.dir, 'community.sqlite3'), 'wb') as f:
            f.write(b'ceci n est pas une base sqlite' * 50)
        r = self.client.get('/healthz')
        self.assertEqual((r.status_code, r.get_json()), (503, {'status': 'error'}))

    def test_readable_community_database_passes(self):
        sqlite3.connect(os.path.join(self.dir, 'community.sqlite3')).execute('CREATE TABLE t(x)').connection.close()
        self.assertEqual(self.client.get('/healthz').status_code, 200)


class TestErrorPages(unittest.TestCase):
    def setUp(self):
        self.client = appmod.app.test_client()

    def test_404_html_for_pages_and_json_for_api(self):
        page = self.client.get('/page-inexistante')
        self.assertEqual(page.status_code, 404)
        self.assertIn('text/html', page.content_type)
        self.assertIn('introuvable', page.get_data(as_text=True))
        api = self.client.get('/api/inexistant')
        self.assertEqual((api.status_code, api.get_json()['status']), (404, 'error'))

    def test_405_lists_allowed_methods(self):
        r = self.client.post('/healthz')
        self.assertEqual(r.status_code, 405)
        self.assertIn('GET', r.headers['Allow'])

    def test_500_hides_technical_details(self):
        appmod.app.config['PROPAGATE_EXCEPTIONS'] = False
        self.addCleanup(appmod.app.config.__setitem__, 'PROPAGATE_EXCEPTIONS', None)
        with unittest.mock.patch.object(appmod, 'present', side_effect=RuntimeError('secret-interne /chemin/x.py')):
            r = self.client.get('/api/articles')
        body = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 500)
        self.assertNotIn('secret-interne', body)
        self.assertNotIn('Traceback', body)


class TestPhotosAndPurge(CollabCase):
    def png(self, size):
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', size, (200, 30, 30)).save(buf, 'PNG')
        buf.seek(0)
        return buf

    def test_large_photo_is_downscaled_to_1600_pixels(self):
        from PIL import Image
        self.register()
        data = {**self.form(), 'photo': (self.png((3000, 2000)), 'preuve.png')}
        r = self.client.post('/api/contributions', data=data, headers=self.csrf())
        self.assertIn(r.status_code, (200, 201), r.get_json())
        files = os.listdir(os.path.join(os.environ['COMPAREPRIX_DATA_DIR'], 'proofs'))
        self.assertEqual(len(files), 1)
        with Image.open(os.path.join(os.environ['COMPAREPRIX_DATA_DIR'], 'proofs', files[0])) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertLessEqual(max(image.size), 1600)
            self.assertEqual(image.size, (1600, 1067))

    def test_small_photo_is_not_enlarged(self):
        from PIL import Image
        self.register()
        data = {**self.form(), 'photo': (self.png((400, 300)), 'preuve.png')}
        self.client.post('/api/contributions', data=data, headers=self.csrf())
        folder = os.path.join(os.environ['COMPAREPRIX_DATA_DIR'], 'proofs')
        with Image.open(os.path.join(folder, os.listdir(folder)[0])) as image:
            self.assertEqual(image.size, (400, 300))

    def test_stale_login_attempts_are_purged_and_active_ones_kept(self):
        self.register()
        path = os.path.join(os.environ['COMPAREPRIX_DATA_DIR'], 'community.sqlite3')
        conn = sqlite3.connect(path)
        conn.execute("INSERT INTO login_attempts VALUES ('perime', 3, 1.0)")
        conn.execute("INSERT INTO login_attempts VALUES ('actif', 3, 99999999999.0)")
        conn.commit()
        conn.close()
        self.client.post('/api/account/login', json={'phone': PHONE, 'password': 'faux'}, headers=self.csrf())
        conn = sqlite3.connect(path)
        identities = {r[0] for r in conn.execute('SELECT identity FROM login_attempts')}
        conn.close()
        self.assertNotIn('perime', identities)
        self.assertIn('actif', identities)


if __name__ == '__main__':
    unittest.main()
