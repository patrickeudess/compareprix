"""Tests du modèle de prix, de l'import CSV et de l'API. Lancer : python -m unittest test_pricing -v"""
import json
import os
import tempfile
import unittest
from datetime import date, timedelta

import import_prices
import pricing
import app as appmod

TODAY = date(2025, 6, 15)


def rec(**kw):
    base = dict(article='Riz 5kg', supermarche='Carrefour', prix=4500, unite='kg',
                date_releve='2025-06-14', source='manuel', statut='valide')
    base.update(kw)
    return base


class TestValidation(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(pricing.validate_article(rec(), TODAY), [])

    def test_rejects_bad_values(self):
        for kw in ({'prix': 0}, {'prix': -5}, {'prix': 12.5}, {'prix': True}, {'unite': 'tonne'},
                   {'date_releve': '15/06/2025'}, {'date_releve': '2025-06-16'},
                   {'source': 'exemple'}, {'statut': 'donnee_exemple'}, {'article': ' '},
                   {'url': 'javascript:alert(1)'}):
            self.assertTrue(pricing.validate_article(rec(**kw), TODAY), kw)


class TestFreshness(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(pricing.freshness(rec(), TODAY), ('recente', 1))
        self.assertEqual(pricing.freshness(rec(date_releve='2025-06-01'), TODAY), ('perimee', 14))
        self.assertEqual(pricing.freshness(rec(date_releve=None), TODAY), ('inconnue', None))
        self.assertEqual(pricing.freshness(rec(statut='donnee_exemple'), TODAY), ('exemple', None))

    def test_legacy_record_is_example_never_dated(self):
        a = pricing.normalize_article({'article': 'Lait', 'supermarche': 'Casino', 'prix': 118})
        self.assertEqual((a['source'], a['statut'], a['date_releve']), ('exemple', 'donnee_exemple', None))


class TestImport(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def csv(self, lines):
        path = os.path.join(self.dir.name, 'r.csv')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('article,supermarche,prix,unite,date_releve,source,statut,url,image_url\n' + '\n'.join(lines) + '\n')
        return path

    def test_all_or_nothing_reports_line_numbers(self):
        rows, errors = import_prices.read_csv(self.csv([
            'Riz,Carrefour,4500,kg,2025-01-01,manuel,valide,,',
            'Huile,Carrefour,abc,L,2025-01-01,manuel,valide,,']))
        self.assertEqual([n for n, _ in errors], [3])
        self.assertEqual(len(rows), 1)

    def test_merge_keeps_most_recent_and_replaces_examples(self):
        existing = [{'article': 'Riz 5kg', 'supermarche': 'Carrefour', 'prix': 1, 'unite': 'kg'},
                    rec(article='Huile', date_releve='2025-06-10')]
        new = [rec(), rec(article='Huile', date_releve='2025-06-01', prix=999)]
        merged, added, updated, skipped = import_prices.merge(existing, new, replace_examples=True)
        self.assertEqual((added, updated, skipped), (1, 0, 1))  # exemple supprimé -> Riz ajouté
        self.assertEqual(sorted(a['article'] for a in merged), ['Huile', 'Riz 5kg'])
        self.assertTrue(all(a['statut'] != 'donnee_exemple' for a in merged))


class TestApi(unittest.TestCase):
    def setUp(self):
        self.client = appmod.app.test_client()
        self.orig = appmod.load_articles
        recent = (date.today() - timedelta(days=1)).isoformat()
        data = [pricing.normalize_article(a) for a in [
            {'article': 'Lait', 'supermarche': 'Casino', 'prix': 118},
            rec(article='Lait réel', date_releve=recent)]]
        appmod.load_articles = lambda: data

    def tearDown(self):
        appmod.load_articles = self.orig

    def test_search_exposes_freshness(self):
        r = self.client.post('/search', data={'search_term': 'lait'}).get_json()['results']
        self.assertEqual({x['article']: x['fraicheur'] for x in r}, {'Lait': 'exemple', 'Lait réel': 'recente'})

    def test_csv_export_has_new_columns(self):
        body = self.client.get('/api/export/csv').get_data(as_text=True)
        self.assertIn('Date relevé,Source,Statut', body.splitlines()[0])


if __name__ == '__main__':
    unittest.main()
