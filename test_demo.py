"""Tests : démonstration statique (GitHub Pages) et point d'entrée WSGI. Lancer : python -m unittest test_demo -v"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(*args, **kw):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=120, **kw)


class TestDemoPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = os.path.join(cls.tmp.name, 'demo.html')
        cls.proc = run(os.path.join(ROOT, 'tools', 'build_demo.py'), '--out', cls.out)
        with open(cls.out, encoding='utf-8') as f:
            cls.html = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_build_succeeds_without_touching_the_repo_database(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(ROOT, 'data', 'compareprix.db-demo')))

    def test_page_is_clearly_labelled_fictional_and_not_indexable(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow">', self.html)
        self.assertIn('fictifs', self.html)
        self.assertTrue(self.html.startswith('<!doctype html>'))

    def test_no_server_needed_and_no_csp_leftovers(self):
        self.assertIn('window.fetch = function', self.html)
        self.assertLess(self.html.index('window.fetch = function'), self.html.rindex('<script>'))  # défini avant l'appli
        self.assertNotIn('nonce', self.html)
        self.assertEqual(re.findall(r'<[^>]*\son[a-z]+\s*=', self.html), [])  # pas de gestionnaire inline
        for secret in ('admin-test-token', 'COMPAREPRIX_ADMIN_TOKEN'):
            self.assertNotIn(secret, self.html)

    def test_demo_data_comes_from_the_real_pricing_code(self):
        self.assertEqual(self.html.count('"supermarche"'), 26)
        self.assertIn('"ecart_pct": 68.1', self.html)      # prix aberrant calculé par pricing.py
        self.assertIn('"prix_unitaire": 900.0', self.html)  # 4 500 FCFA / 5 kg

    def test_default_output_never_overwrites_the_public_index_page(self):
        # index.html (page publique de GitHub Pages) est maintenue à part : l'exécution par défaut écrit dans build/
        with open(os.path.join(ROOT, 'index.html'), 'rb') as f:
            before = f.read()
        proc = run(os.path.join(ROOT, 'tools', 'build_demo.py'))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.addCleanup(lambda: os.path.exists(os.path.join(ROOT, 'build', 'demo.html')) and
                        os.remove(os.path.join(ROOT, 'build', 'demo.html')))
        with open(os.path.join(ROOT, 'index.html'), 'rb') as f:
            self.assertEqual(f.read(), before)
        self.assertTrue(os.path.exists(os.path.join(ROOT, 'build', 'demo.html')))

    def test_nojekyll_present(self):
        self.assertTrue(os.path.exists(os.path.join(ROOT, '.nojekyll')))


class TestWsgi(unittest.TestCase):
    def test_works_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as elsewhere, tempfile.TemporaryDirectory() as dbdir:
            code = ("import sys; sys.path.insert(0, %r); import os, wsgi; "
                    "print(os.getcwd() == %r, callable(wsgi.application))") % (ROOT, ROOT)
            env = {**os.environ, 'COMPAREPRIX_DB': os.path.join(dbdir, 'w.db')}
            r = run('-c', code, cwd=elsewhere, env=env)
            self.assertEqual(r.stdout.strip().splitlines()[-1], 'True True', r.stderr)


if __name__ == '__main__':
    unittest.main()
