"""Tests : mise à jour des pages de redirection GitHub Pages (tools/set_site_url.py).
Lancer : python -m unittest test_set_site_url -v"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
import set_site_url as su

ROOT = os.path.dirname(os.path.abspath(__file__))


class TestSetSiteUrl(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name in su.PAGES:
            shutil.copy(os.path.join(ROOT, name), self.tmp.name)

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = su.main(list(argv), root=self.tmp.name)
        return code, out.getvalue()

    def text(self, name):
        return su.read(os.path.join(self.tmp.name, name))

    def test_old_address_is_detected_from_index(self):
        self.assertTrue(su.detect_old(self.tmp.name).startswith('https://'))

    def test_dry_run_changes_nothing_and_counts_occurrences(self):
        before = {n: self.text(n) for n in su.PAGES}
        code, out = self.run_main('https://www.exemple.ci')
        self.assertEqual(code, 0)
        self.assertIn('Simulation uniquement', out)
        self.assertEqual(before, {n: self.text(n) for n in su.PAGES})

    def test_apply_rewrites_every_page_and_leaves_no_old_address(self):
        old = su.detect_old(self.tmp.name)
        self.run_main('https://www.exemple.ci/', '--apply')
        for name in su.PAGES:
            content = self.text(name)
            self.assertNotIn(old, content, name)
            self.assertIn('https://www.exemple.ci', content, name)
            self.assertNotIn('exemple.ci//', content, name)  # l'adresse saisie avec « / » final ne crée pas de double barre

    def test_paths_and_redirect_logic_are_preserved(self):
        before = self.text('panier.html')
        self.run_main('https://www.exemple.ci', '--apply')
        after = self.text('panier.html')
        self.assertIn('"/panier.html"', after)
        self.assertEqual(before.replace(su.detect_old(ROOT), 'https://www.exemple.ci'), after)

    def test_second_run_is_a_no_op(self):
        self.run_main('https://www.exemple.ci', '--apply')
        code, out = self.run_main('https://www.exemple.ci', '--apply')
        self.assertIn('déjà', out)

    def test_invalid_addresses_are_refused(self):
        for bad in ('http://www.exemple.ci', 'www.exemple.ci', 'https://exemple.ci/chemin', 'https://', 'https://exemple', 'javascript:alert(1)',
                    "https://a.ci'><script>alert(1)</script>"):
            with self.assertRaises(SystemExit, msg=bad), contextlib.redirect_stderr(io.StringIO()):
                su.main([bad], root=self.tmp.name)

    def test_line_endings_and_encoding_are_kept(self):
        raw = open(os.path.join(self.tmp.name, 'index.html'), 'rb').read()
        self.run_main('https://www.exemple.ci', '--apply')
        new = open(os.path.join(self.tmp.name, 'index.html'), 'rb').read()
        self.assertEqual(raw.count(b'\r\n'), new.count(b'\r\n'))
        new.decode('utf-8')


if __name__ == '__main__':
    unittest.main()
