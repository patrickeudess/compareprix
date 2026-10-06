"""Tests : en-têtes de sécurité, CSP à nonce, absence de JS inline, healthcheck, IP spoofing.
Lancer : python -m unittest test_security -v"""
import atexit
import os
import re
import tempfile
import unittest

_TMP = tempfile.TemporaryDirectory()
atexit.register(_TMP.cleanup)  # nettoyage propre à la sortie
os.environ['COMPAREPRIX_DB'] = os.path.join(_TMP.name, 'sec.db')

import app as appmod
import db
from ratelimit import SlidingWindowLimiter


def setUpModule():
    """Base propre à ce module : la variable d'environnement est partagée entre modules de tests."""
    os.environ['COMPAREPRIX_DB'] = os.path.join(_TMP.name, 'sec.db')
    db.init_db(seed=False)


class TestHeaders(unittest.TestCase):
    def setUp(self):
        self.client = appmod.app.test_client()

    def test_security_headers_present_on_all_responses(self):
        for url in ('/', '/admin', '/healthz', '/api/articles', '/static/css/style.css'):
            with self.client.get(url) as response:  # ferme le flux (fichiers statiques)
                self.assertEqual(response.status_code, 200, url)  # pas de test « à vide » sur une page en erreur
                h = response.headers
            self.assertEqual(h['X-Content-Type-Options'], 'nosniff', url)
            self.assertEqual(h['X-Frame-Options'], 'DENY', url)
            self.assertIn('Referrer-Policy', h, url)
            self.assertIn("frame-ancestors 'none'", h['Content-Security-Policy'], url)
            self.assertIn("object-src 'none'", h['Content-Security-Policy'], url)

    def test_csp_has_no_unsafe_inline_for_scripts(self):
        csp = self.client.get('/').headers['Content-Security-Policy']
        script_src = [d for d in csp.split('; ') if d.startswith('script-src')][0]
        self.assertNotIn('unsafe-inline', script_src)
        self.assertNotIn('unsafe-eval', script_src)

    def test_nonce_is_fresh_per_request_and_matches_the_page(self):
        pages = [self.client.get('/') for _ in range(2)]
        nonces = [re.search(r"'nonce-([^']+)'", p.headers['Content-Security-Policy']).group(1) for p in pages]
        self.assertNotEqual(*nonces)
        for page, nonce in zip(pages, nonces):
            self.assertIn(f'<script nonce="{nonce}">', page.get_data(as_text=True))

    def test_hsts_only_when_enabled(self):
        self.assertNotIn('Strict-Transport-Security', self.client.get('/').headers)
        os.environ['COMPAREPRIX_HSTS'] = '1'
        self.addCleanup(os.environ.pop, 'COMPAREPRIX_HSTS', None)
        self.assertIn('max-age=', self.client.get('/').headers['Strict-Transport-Security'])


class TestTemplate(unittest.TestCase):
    def test_no_inline_event_handlers_or_unnonced_scripts(self):
        for path in ('templates/index.html', 'templates/admin.html'):
            with open(path, encoding='utf-8') as f:
                html = f.read()
            # attributs onclick=, onerror=... (hors propriétés JS comme reader.onload =)
            self.assertEqual(re.findall(r'<[^>]*\son[a-z]+\s*=', html), [], path)
            self.assertEqual(re.findall(r'<script(?![^>]*nonce=)[^>]*>', html), [], path)
            self.assertNotIn('javascript:', re.sub(r'//.*', '', html).replace("bloque javascript:", ''), path)

    def test_admin_page_never_uses_innerhtml(self):
        # la page d'admin affiche des données saisies par des tiers (signalements) : DOM + textContent uniquement
        with open('templates/admin.html', encoding='utf-8') as f:
            html = f.read()
        usages = re.findall(r'\.\s*(?:innerHTML|outerHTML)\b|insertAdjacentHTML\s*\(|document\.write(?:ln)?\s*\(', html)
        self.assertEqual(usages, [])  # les commentaires qui citent ces mots ne comptent pas


class TestHealth(unittest.TestCase):
    def test_ok_and_503_when_db_unavailable(self):
        client = appmod.app.test_client()
        self.assertEqual(client.get('/healthz').get_json(), {'status': 'ok'})
        old = os.environ['COMPAREPRIX_DB']
        os.environ['COMPAREPRIX_DB'] = '/proc/inexistant/impossible.db'
        try:
            with self.assertLogs(appmod.app.logger, 'ERROR'):  # l'échec est journalisé côté serveur
                r = client.get('/healthz')
        finally:
            os.environ['COMPAREPRIX_DB'] = old
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.get_json(), {'status': 'error'})  # aucun détail interne exposé


class TestIpSpoofing(unittest.TestCase):
    def test_x_forwarded_for_ignored_by_default(self):
        self.assertEqual(appmod._TRUSTED_PROXIES, 0)
        db.init_db(seed=False)
        appmod.FEEDBACK_LIMITER = SlidingWindowLimiter(2, 3600)
        client = appmod.app.test_client()
        form = dict(product_name='P', supermarket='S', current_price='1', new_price='2', feedback_type='t')
        codes = [client.post('/submit_feedback', data=form, headers={'X-Forwarded-For': f'9.9.9.{i}'}).status_code
                 for i in range(3)]
        self.assertEqual(codes, [200, 200, 429])  # changer d'en-tête ne contourne pas la limite


if __name__ == '__main__':
    unittest.main()
