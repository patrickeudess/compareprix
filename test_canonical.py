"""Tests : redirection vers l'adresse officielle (app.redirect_to_canonical_host).
Lancer : python -m unittest test_canonical -v"""
import atexit
import os
import tempfile
import unittest
import unittest.mock

_TMP = tempfile.TemporaryDirectory()
atexit.register(_TMP.cleanup)
os.environ.setdefault('COMPAREPRIX_DB', os.path.join(_TMP.name, 'c.db'))

import db
import app as appmod

CANON = {'COMPAREPRIX_CANONICAL_HOST': 'www.exemple.ci'}


class TestCanonicalHost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(self.tmp.name, 'c.db')
        db.init_db(seed=False)
        self.client = appmod.app.test_client()
        patcher = unittest.mock.patch.dict(os.environ, CANON)
        patcher.start()
        self.addCleanup(patcher.stop)

    def get(self, path, host, **kw):
        r = self.client.get(path, headers={'Host': host}, **kw)
        self.addCleanup(r.close)
        return r

    def test_other_host_is_redirected_permanently_keeping_path_and_query(self):
        r = self.get('/compte?intent=contribute', 'patrickeudess.pythonanywhere.com')
        self.assertEqual((r.status_code, r.headers['Location']), (301, 'https://www.exemple.ci/compte?intent=contribute'))
        self.assertEqual(self.get('/', 'exemple.ci').headers['Location'], 'https://www.exemple.ci/')

    def test_canonical_host_is_served_normally_whatever_the_case_or_port(self):
        for host in ('www.exemple.ci', 'WWW.EXEMPLE.CI', 'www.exemple.ci:443'):
            self.assertEqual(self.get('/', host).status_code, 200, host)

    def test_healthcheck_and_local_access_are_never_redirected(self):
        self.assertEqual(self.get('/healthz', 'patrickeudess.pythonanywhere.com').status_code, 200)
        for host in ('localhost', 'localhost:8000', '127.0.0.1:5000'):
            self.assertEqual(self.get('/', host).status_code, 200, host)

    def test_writes_are_not_redirected(self):
        r = self.client.post('/search', data={'search_term': 'riz'}, headers={'Host': 'patrickeudess.pythonanywhere.com'})
        self.assertEqual(r.status_code, 200)

    def test_inactive_without_the_variable(self):
        with unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_CANONICAL_HOST': ''}):
            self.assertEqual(self.get('/', 'patrickeudess.pythonanywhere.com').status_code, 200)

    def test_pasted_url_forms_are_tolerated(self):
        for raw in ('https://www.exemple.ci', 'https://www.exemple.ci/', 'WWW.exemple.ci/', ' www.exemple.ci '):
            with unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_CANONICAL_HOST': raw}):
                self.assertEqual(appmod.canonical_host(), 'www.exemple.ci', raw)
                self.assertEqual(self.get('/', 'www.exemple.ci').status_code, 200, raw)

    def test_redirect_still_carries_the_security_headers(self):
        r = self.get('/', 'autre.exemple.org')
        self.assertIn('Content-Security-Policy', r.headers)


if __name__ == '__main__':
    unittest.main()
