"""Tests : compression gzip des réponses publiques volumineuses (app.compress_response).
Lancer : python -m unittest test_compression -v"""
import atexit
import gzip
import json
import os
import tempfile
import unittest

_TMP = tempfile.TemporaryDirectory()
atexit.register(_TMP.cleanup)
os.environ.setdefault('COMPAREPRIX_DB', os.path.join(_TMP.name, 'gz.db'))

import db
import app as appmod

GZ = {'Accept-Encoding': 'gzip, deflate'}


class TestGzip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(self.tmp.name, 'g.db')
        db.init_db(seed=False)
        with db.transaction() as conn:
            for i in range(40):
                db.add_observation(conn, dict(article=f'Produit numéro {i} 1kg', supermarche='Carrefour', prix=1000 + i, unite='kg',
                                              date_releve='2026-10-01', source='manuel', statut='valide'))
        self.client = appmod.app.test_client()

    def get(self, path, **kw):
        # le client de test ne ferme pas les fichiers statiques (le serveur WSGI, lui, ferme la réponse)
        response = self.client.get(path, **kw)
        self.addCleanup(response.close)
        return response

    def test_catalogue_json_is_compressed_and_identical_once_decompressed(self):
        plain = self.get('/api/articles')
        packed = self.get('/api/articles', headers=GZ)
        self.assertNotIn('Content-Encoding', plain.headers)
        self.assertEqual(packed.headers['Content-Encoding'], 'gzip')
        self.assertIn('Accept-Encoding', packed.headers['Vary'])
        self.assertLess(len(packed.data), len(plain.data) / 3)
        self.assertEqual(json.loads(gzip.decompress(packed.data)), json.loads(plain.data))
        self.assertEqual(int(packed.headers['Content-Length']), len(packed.data))

    def test_static_assets_are_compressed_and_identical(self):
        for path in ('/static/product-design.css', '/static/compareprix.js'):
            plain, packed = self.get(path), self.get(path, headers=GZ)
            self.assertEqual(packed.headers['Content-Encoding'], 'gzip', path)
            self.assertEqual(gzip.decompress(packed.data), plain.data, path)
            self.assertTrue(packed.headers['Content-Type'].startswith(plain.headers['Content-Type'].split(';')[0]))

    def test_etag_stays_usable_for_revalidation(self):
        first = self.get('/static/product-design.css', headers=GZ)
        etag = first.headers['ETag']
        self.assertTrue(etag.startswith('W/'))
        again = self.get('/static/product-design.css', headers={**GZ, 'If-None-Match': etag})
        self.assertEqual(again.status_code, 304)

    def test_responses_carrying_tokens_or_sessions_are_never_compressed(self):
        for path in ('/api/session', '/healthz', '/', '/compte'):
            r = self.get(path, headers=GZ)
            self.assertNotIn('Content-Encoding', r.headers, path)

    def test_client_without_gzip_support_gets_plain_content(self):
        self.assertNotIn('Content-Encoding', self.get('/static/compareprix.js', headers={'Accept-Encoding': 'identity'}).headers)

    def test_small_responses_and_errors_are_left_alone(self):
        self.assertNotIn('Content-Encoding', self.get('/api/references', headers=GZ).headers)  # < 1 Ko
        self.assertEqual(self.get('/static/inexistant.js', headers=GZ).status_code, 404)

    def test_search_results_are_compressed_when_large(self):
        r = self.client.post('/search', data={'search_term': 'produit'}, headers=GZ)
        self.assertEqual(r.headers.get('Content-Encoding'), 'gzip')
        self.assertEqual(len(json.loads(gzip.decompress(r.data))['results']), 40)


if __name__ == '__main__':
    unittest.main()
