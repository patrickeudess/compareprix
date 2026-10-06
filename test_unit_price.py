"""Tests : quantités, prix unitaire, prix aberrants, validation du contenu des photos.
Lancer : python -m unittest test_unit_price -v"""
import io
import os
import tempfile
import unittest

_TMP = tempfile.TemporaryDirectory()
os.environ['COMPAREPRIX_DB'] = os.path.join(_TMP.name, 'boot.db')

import db
import app as appmod
from pricing import enrich_results, parse_quantity, unit_price
from ratelimit import SlidingWindowLimiter
from uploads import detect_image_extension

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
JPG = b'\xff\xd8\xff\xe0' + b'\x00' * 32


class TestQuantity(unittest.TestCase):
    def test_formats(self):
        cases = {'Riz 5kg': (5, 'kg'), 'Riz 5 Kg': (5, 'kg'), 'Lait 750ml': (0.75, 'L'),
                 'Lait 6x1L': (6, 'L'), 'Pâtes 12x500g': (6, 'kg'), 'Eau 1,5 L': (1.5, 'L'),
                 'Huile 2 litres': (2, 'L'), 'Sucre 500g': (0.5, 'kg')}
        for name, (value, base) in cases.items():
            q = parse_quantity(name)
            self.assertAlmostEqual(q.value, value, msg=name)
            self.assertEqual(q.base, base, name)
        self.assertAlmostEqual(parse_quantity('Coca 33cl x6').value, 1.98)

    def test_no_quantity(self):
        for name in ('Riz', 'Lait entier', 'Savon 2 en 1', '', None):
            self.assertIsNone(parse_quantity(name), name)


class TestUnitPrice(unittest.TestCase):
    def test_package_price_divided(self):
        self.assertEqual(unit_price({'article': 'Riz 5kg', 'prix': 4500, 'unite': 'kg'}), (900.0, 'kg', 'nom'))
        self.assertEqual(unit_price({'article': 'Lait 6x1L', 'prix': 3000, 'unite': 'L'}), (500.0, 'L', 'nom'))

    def test_legacy_declared_unit_is_per_unit(self):
        self.assertEqual(unit_price({'article': 'Riz Basmati', 'prix': 500, 'unite': 'kg'}), (500.0, 'kg', 'declare'))
        self.assertEqual(unit_price({'article': 'Pain', 'prix': 85, 'unite': 'unité'}), (85.0, 'unité', 'declare'))

    def test_guessed_unit_of_scraped_product_is_not_trusted(self):
        a = {'article': 'Riz Sunrise', 'prix': 4500, 'unite': 'kg', 'source': 'jumia'}
        self.assertEqual(unit_price(a), (None, None, None))
        self.assertEqual(unit_price({**a, 'article': 'Riz Sunrise 5kg'})[0], 900.0)

    def test_not_comparable(self):
        self.assertEqual(unit_price({'article': 'Pack', 'prix': 100, 'unite': 'lot'}), (None, None, None))
        self.assertEqual(unit_price({'article': 'X', 'prix': 0, 'unite': 'kg'}), (None, None, None))


def art(name, store, prix, unite='kg', **kw):
    return {'article': name, 'supermarche': store, 'prix': prix, 'unite': unite, **kw}


class TestEnrich(unittest.TestCase):
    def test_best_price_uses_unit_price_not_sticker_price(self):
        r = enrich_results([art('Riz 5kg', 'A', 4500), art('Riz 1kg', 'B', 1100)])
        best = {x['supermarche']: x['meilleur_prix'] for x in r}
        self.assertEqual(best, {'A': True, 'B': False})  # 900 FCFA/kg < 1100 FCFA/kg, malgré 4500 > 1100

    def test_best_price_is_per_base_unit(self):
        r = enrich_results([art('Riz 5kg', 'A', 4500), art('Lait 1L', 'A', 700, 'L')])
        self.assertTrue(all(x['meilleur_prix'] for x in r))  # un gagnant par groupe kg / L

    def test_anomaly_vs_median(self):
        r = enrich_results([art('Lait', 'A', 100), art('Lait', 'B', 105), art('Lait', 'C', 190)], 20)
        flagged = {x['supermarche']: x['anomalie'] for x in r}
        self.assertIsNone(flagged['A'])
        self.assertIsNone(flagged['B'])
        self.assertEqual(flagged['C'], {'ecart_pct': 81.0, 'mediane': 105.0})

    def test_no_anomaly_below_three_points_or_within_threshold(self):
        two = enrich_results([art('Lait', 'A', 100), art('Lait', 'B', 300)], 20)
        self.assertTrue(all(x['anomalie'] is None for x in two))
        three = enrich_results([art('Lait', 'A', 100), art('Lait', 'B', 110), art('Lait', 'C', 118)], 20)
        self.assertTrue(all(x['anomalie'] is None for x in three))

    def test_anomaly_compares_unit_prices(self):
        r = enrich_results([art('Eau 1,5L', 'A', 150, 'L'), art('Eau 1,5L', 'B', 150, 'L'),
                            art('Eau 1,5L', 'C', 450, 'L')], 20)
        self.assertEqual([bool(x['anomalie']) for x in r], [False, False, True])

    def test_config_threshold_is_read(self):
        from pricing import load_max_deviation
        self.assertEqual(load_max_deviation(), 20.0)
        self.assertEqual(load_max_deviation('/inexistant.json'), 20)

    def test_seed_data_has_no_false_alarm(self):
        # Les 21 lignes d'exemple (prix proches entre magasins) ne doivent rien signaler
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(tmp.name, 's.db')
        db.init_db()
        r = enrich_results(db.list_current())
        self.assertEqual([x['article'] for x in r if x['anomalie']], [])


class TestPhotoValidation(unittest.TestCase):
    def test_signatures(self):
        self.assertEqual(detect_image_extension(PNG), 'png')
        self.assertEqual(detect_image_extension(JPG), 'jpg')
        self.assertEqual(detect_image_extension(b'GIF89a....'), 'gif')
        for bad in (b'<?php echo 1;', b'<svg onload=alert(1)>', b'MZ\x90\x00', b'', b'%PDF-1.4'):
            self.assertIsNone(detect_image_extension(bad), bad)


class TestPhotoHttp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(self.tmp.name, 'p.db')
        db.init_db(seed=False)
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)  # les photos sont écrites en chemin relatif data/user_photos
        self.addCleanup(os.chdir, self.cwd)
        appmod.FEEDBACK_LIMITER = SlidingWindowLimiter(100, 3600)
        self.client = appmod.app.test_client()

    def post(self, content, filename):
        data = dict(product_name='Pain', supermarket='Carrefour', current_price='85', new_price='70',
                    feedback_type='price_decrease', photo=(io.BytesIO(content), filename))
        return self.client.post('/submit_feedback', data=data, content_type='multipart/form-data')

    def saved(self):
        d = os.path.join(self.tmp.name, 'data', 'user_photos')
        return os.listdir(d) if os.path.isdir(d) else []

    def test_real_image_accepted_extension_comes_from_content(self):
        r = self.post(PNG, 'ticket.jpg')  # nom trompeur : le contenu fait foi
        self.assertEqual(r.status_code, 200)
        self.assertEqual([f.rsplit('.', 1)[1] for f in self.saved()], ['png'])

    def test_disguised_script_rejected_nothing_saved_nothing_stored(self):
        for payload, name in ((b'<?php system($_GET[1]); ?>', 'x.png'), (b'<svg onload=alert(1)>', 'x.jpg')):
            r = self.post(payload, name)
            self.assertEqual(r.status_code, 400)
            self.assertIn('image', r.get_json()['message'])
        self.assertEqual(self.saved(), [])
        self.assertEqual(db.list_feedback(), [])

    def test_oversized_image_rejected(self):
        r = self.post(PNG + b'\x00' * (5 * 1024 * 1024), 'big.png')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.saved(), [])

    def test_no_photo_is_fine(self):
        data = dict(product_name='Pain', supermarket='Carrefour', current_price='85', new_price='70',
                    feedback_type='price_decrease')
        self.assertEqual(self.client.post('/submit_feedback', data=data).status_code, 200)


class TestApiPayload(unittest.TestCase):
    def test_search_returns_unit_fields(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(tmp.name, 'a.db')
        db.init_db(seed=False)
        with db.transaction() as c:
            db.import_articles(c, [art('Riz 5kg', 'A', 4500, date_releve='2025-06-10', source='manuel', statut='valide'),
                                   art('Riz 1kg', 'B', 1100, date_releve='2025-06-10', source='manuel', statut='valide')])
        client = appmod.app.test_client()
        res = {r['article']: r for r in client.post('/search', data={'search_term': 'riz'}).get_json()['results']}
        self.assertEqual((res['Riz 5kg']['prix_unitaire'], res['Riz 5kg']['meilleur_prix']), (900.0, True))
        self.assertEqual((res['Riz 1kg']['prix_unitaire'], res['Riz 1kg']['meilleur_prix']), (1100.0, False))
        csv_head = client.get('/api/export/csv').get_data(as_text=True).splitlines()[0]
        self.assertIn('Prix unitaire,Unité de base', csv_head)


if __name__ == '__main__':
    unittest.main()
