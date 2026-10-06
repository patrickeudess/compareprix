"""Tests : administration (saisie, import CSV, photos, modération), statistiques unitaires, fiche de collecte.
Lancer : python -m unittest test_admin -v"""
import atexit
import io
import os
import tempfile
import unittest
from datetime import date

_TMP = tempfile.TemporaryDirectory()
atexit.register(_TMP.cleanup)
os.environ['COMPAREPRIX_DB'] = os.path.join(_TMP.name, 'boot.db')

import app as appmod
import db
import import_prices
from pricing import enrich_results, store_price_index, unit_stats
from ratelimit import SlidingWindowLimiter

AUTH = {'Authorization': 'Bearer admin-test-token'}
TODAY = date.today().isoformat()
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
HEADER = 'article,supermarche,prix,unite,date_releve,source,statut,url,image_url\n'


def obs(article='Riz parfumé 5kg', supermarche='Carrefour', prix=4500, **kw):
    base = dict(article=article, supermarche=supermarche, prix=prix, unite='kg', date_releve=TODAY,
                source='manuel', statut='a_verifier')
    base.update(kw)
    return base


class AdminCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(self.tmp.name, 'a.db')
        os.environ['COMPAREPRIX_ADMIN_TOKEN'] = 'admin-test-token'
        self.addCleanup(os.environ.pop, 'COMPAREPRIX_ADMIN_TOKEN', None)
        db.init_db(seed=False)
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)  # backups et photos en chemins relatifs
        self.addCleanup(os.chdir, self.cwd)
        appmod.ADMIN_FAIL_LIMITER = SlidingWindowLimiter(1000, 600)
        appmod.FEEDBACK_LIMITER = SlidingWindowLimiter(1000, 600)
        self.client = appmod.app.test_client()


class TestAuth(AdminCase):
    def test_every_admin_endpoint_requires_the_token(self):
        calls = [('get', '/api/observations'), ('post', '/api/observations'), ('put', '/api/observations/1'),
                 ('delete', '/api/observations/1'), ('post', '/api/observations/import'),
                 ('get', '/api/feedback'), ('get', '/api/feedback/x/photo')]
        for method, url in calls:
            self.assertEqual(getattr(self.client, method)(url).status_code, 401, (method, url))
            bad = getattr(self.client, method)(url, headers={'Authorization': 'Bearer faux'})
            self.assertEqual(bad.status_code, 401, (method, url))

    def test_token_guessing_is_throttled(self):
        appmod.ADMIN_FAIL_LIMITER = SlidingWindowLimiter(3, 600)
        codes = [self.client.get('/api/observations', headers={'Authorization': 'Bearer x'}).status_code for _ in range(5)]
        self.assertEqual(codes, [401, 401, 401, 429, 429])

    def test_admin_page_is_public_shell_without_data(self):
        r = self.client.get('/admin')
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn('nonce="', html)
        self.assertNotIn('admin-test-token', html)


class TestObservations(AdminCase):
    def post(self, **kw):
        return self.client.post('/api/observations', json=obs(**kw), headers=AUTH)

    def test_create_returns_unit_price_and_is_visible_in_search(self):
        r = self.post()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()['prix_unitaire'], 900.0)
        found = self.client.post('/search', data={'search_term': 'riz'}).get_json()['results']
        self.assertEqual((found[0]['prix'], found[0]['statut']), (4500, 'a_verifier'))

    def test_prix_as_string_from_form_is_accepted_and_duplicate_flagged(self):
        self.assertEqual(self.post(prix='4500').status_code, 201)
        again = self.post(prix='4500')
        self.assertEqual((again.status_code, again.get_json()['created']), (200, False))

    def test_invalid_input_is_rejected_with_reasons(self):
        for kw in ({'prix': 0}, {'prix': 'abc'}, {'unite': 'tonne'}, {'date_releve': '2999-01-01'},
                   {'source': 'exemple'}, {'article': ''}, {'url': 'javascript:alert(1)'}):
            r = self.post(**kw)
            self.assertEqual(r.status_code, 400, kw)
            self.assertTrue(r.get_json()['errors'], kw)
        self.assertEqual(db.list_current(), [])

    def test_aberrant_price_is_flagged_immediately(self):
        for store, prix in (('Carrefour', 4500), ('Cap Sud', 4700)):
            self.post(supermarche=store, prix=prix)
        warn = self.post(supermarche='Casino', prix=7900).get_json()
        self.assertEqual(warn['anomalie']['ecart_pct'], 68.1)
        self.assertIsNone(self.post(supermarche='Marché', prix=4600).get_json()['anomalie'])

    def test_validate_then_delete_then_protect_referenced(self):
        oid = self.post().get_json()['observation_id']
        self.assertEqual(self.client.put(f'/api/observations/{oid}', json={'statut': 'valide'}, headers=AUTH).status_code, 200)
        self.assertEqual(self.client.put(f'/api/observations/{oid}', json={'statut': 'nimporte'}, headers=AUTH).status_code, 400)
        self.assertEqual(db.list_current()[0]['statut'], 'valide')
        self.assertEqual(self.client.delete(f'/api/observations/{oid}', headers=AUTH).status_code, 200)
        self.assertEqual(self.client.delete(f'/api/observations/{oid}', headers=AUTH).status_code, 404)
        # un relevé créé par un signalement approuvé ne peut pas être supprimé
        with db.transaction() as c:
            db.add_observation(c, obs(date_releve='2025-01-01'))
        db.add_feedback(dict(id='f1', timestamp='t', date='2025-06-12', product_name='Riz parfumé 5kg', supermarket='Carrefour',
                             current_price=4500, new_price=4000, price_difference=-500, feedback_type='x', status='pending_review'))
        applied = db.set_feedback_status('f1', 'approved')['observation_id']
        self.assertEqual(self.client.delete(f'/api/observations/{applied}', headers=AUTH).status_code, 409)

    def test_example_data_cannot_be_validated_or_deleted_by_status_route(self):
        with db.transaction() as c:
            db.add_observation(c, {'article': 'Lait', 'supermarche': 'Casino', 'prix': 118})
        oid = db.recent_observations()[0]['id']
        self.assertEqual(self.client.put(f'/api/observations/{oid}', json={'statut': 'valide'}, headers=AUTH).status_code, 404)

    def test_recent_lists_newest_first_with_current_flag(self):
        self.post(prix=4000, date_releve='2025-01-01')
        self.post(prix=4500)
        self.post(prix=3000, date_releve='2024-01-01')  # saisi en dernier mais ancien : pas le prix courant
        rows = self.client.get('/api/observations', headers=AUTH).get_json()['observations']
        self.assertEqual([(r['prix'], bool(r['courant'])) for r in rows], [(3000, False), (4500, True), (4000, False)])


class TestImportEndpoint(AdminCase):
    def upload(self, content, apply=False, encoding='utf-8'):
        data = {'file': (io.BytesIO(content.encode(encoding) if isinstance(content, str) else content), 'r.csv')}
        if apply:
            data['apply'] = '1'
        return self.client.post('/api/observations/import', data=data, headers=AUTH, content_type='multipart/form-data')

    def test_dry_run_writes_nothing_then_apply_writes_and_backs_up(self):
        csv_text = HEADER + f'Riz parfumé 5kg,Carrefour,4500,kg,{TODAY},manuel,a_verifier,,\n'
        r = self.upload(csv_text)
        self.assertEqual((r.status_code, r.get_json()['applique'], r.get_json()['resultat']['ajoutes']), (200, False, 1))
        self.assertEqual(db.list_current(), [])
        r = self.upload(csv_text, apply=True)
        self.assertTrue(r.get_json()['applique'])
        self.assertEqual(len(db.list_current()), 1)
        self.assertTrue([f for f in os.listdir('data/backups') if f.startswith('avant_import_web_')])

    def test_all_or_nothing_with_line_numbers(self):
        r = self.upload(HEADER + f'Riz,Carrefour,4500,kg,{TODAY},manuel,a_verifier,,\nHuile,Casino,abc,L,{TODAY},manuel,a_verifier,,\n', apply=True)
        self.assertEqual(r.status_code, 400)
        self.assertEqual([e['ligne'] for e in r.get_json()['erreurs']], [3])
        self.assertEqual(db.list_current(), [])

    def test_rows_without_price_are_skipped_not_rejected(self):
        r = self.upload(HEADER + f'Riz,Carrefour,,kg,,manuel,a_verifier,,\nHuile,Casino,900,L,{TODAY},manuel,a_verifier,,\n', apply=True)
        self.assertEqual((r.status_code, r.get_json()['lignes_sans_prix_ignorees'], r.get_json()['lignes_valides']), (200, 1, 1))

    def test_french_excel_semicolon_and_cp1252(self):
        header = HEADER.replace(',', ';')
        row = f'Pâtes à l\'œuf 500g;Casino;450;kg;{TODAY};manuel;a_verifier;;\n'
        r = self.upload(header + row, apply=True, encoding='cp1252')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(db.list_current()[0]['article'], "Pâtes à l'œuf 500g")  # accents intacts

    def test_utf8_bom_and_missing_columns_and_size(self):
        self.assertEqual(self.upload('﻿' + HEADER + f'Riz,A,10,kg,{TODAY},manuel,valide,,\n').status_code, 200)
        r = self.upload('article,prix\nRiz,10\n')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Colonnes manquantes', r.get_json()['message'])
        old = appmod.MAX_IMPORT_BYTES
        appmod.MAX_IMPORT_BYTES = 100  # limite abaissée : évite un corps de 2 Mo (fichier temporaire du client de test)
        self.addCleanup(setattr, appmod, 'MAX_IMPORT_BYTES', old)
        self.assertEqual(self.upload(b'x' * 200).status_code, 413)
        self.assertEqual(self.client.post('/api/observations/import', headers=AUTH).status_code, 400)

    def test_collection_sheet_is_importable_and_blank(self):
        with open('/'.join([self.cwd, 'data', 'fiche_collecte.csv']), 'rb') as f:
            raw = f.read()
        rows, errors, skipped = import_prices.parse_csv(io.StringIO(import_prices.decode_csv(raw)))
        self.assertEqual((rows, errors, skipped), ([], [], 90))  # 30 produits x 3 magasins, aucun prix inventé
        filled = raw.decode('utf-8-sig').replace('Riz parfumé 5kg,Carrefour,,kg,,', f'Riz parfumé 5kg,Carrefour,4500,kg,{TODAY},', 1)
        rows, errors, skipped = import_prices.parse_csv(io.StringIO(filled))
        self.assertEqual((len(rows), errors, skipped), (1, [], 89))


class TestPhotoEndpoint(AdminCase):
    def test_photo_served_to_admin_only_and_traversal_blocked(self):
        os.makedirs('data/user_photos')
        good = 'feedback_' + 'a' * 32 + '.png'
        with open(os.path.join('data/user_photos', good), 'wb') as f:
            f.write(PNG)
        secret = os.path.join(self.tmp.name, 'secret.txt')
        with open(secret, 'w') as f:
            f.write('secret')
        base = dict(timestamp='t', date='2025-06-12', product_name='P', supermarket='S', current_price=1, new_price=2,
                    price_difference=1, feedback_type='x', status='pending_review')
        db.add_feedback({**base, 'id': 'ok1', 'photo_path': 'data/user_photos/' + good})
        db.add_feedback({**base, 'id': 'evil1', 'photo_path': '../../secret.txt'})
        db.add_feedback({**base, 'id': 'evil2', 'photo_path': secret})
        db.add_feedback({**base, 'id': 'none1', 'photo_path': None})
        self.assertEqual(self.client.get('/api/feedback/ok1/photo').status_code, 401)
        r = self.client.get('/api/feedback/ok1/photo', headers=AUTH)
        self.assertEqual((r.status_code, r.mimetype, r.data[:4]), (200, 'image/png', PNG[:4]))
        r.close()
        for fid in ('evil1', 'evil2', 'none1', 'inconnu'):
            self.assertEqual(self.client.get(f'/api/feedback/{fid}/photo', headers=AUTH).status_code, 404, fid)


def art(name, store, prix, unite='kg'):
    return {'article': name, 'supermarche': store, 'prix': prix, 'unite': unite, 'source': 'manuel', 'statut': 'valide'}


class TestStats(unittest.TestCase):
    def test_unit_stats_compare_packages_not_sticker_prices(self):
        e = enrich_results([art('Riz 5kg', 'A', 4500), art('Riz 1kg', 'B', 1100), art('Riz 25kg', 'C', 20000),
                            art('Lait 1L', 'A', 700, 'L'), art('Pack', 'A', 100, 'lot')])
        s = unit_stats(e)
        self.assertEqual((s['kg']['count'], s['kg']['min'], s['kg']['median'], s['kg']['max']), (3, 800.0, 900.0, 1100.0))
        self.assertEqual(s['kg']['moins_cher'], {'article': 'Riz 25kg', 'supermarche': 'C', 'prix_unitaire': 800.0})
        self.assertEqual(s['kg']['ecart_pct'], 37.5)
        self.assertEqual(s['L']['count'], 1)
        self.assertNotIn('lot', s)  # non comparable : exclu

    def test_store_index_100_is_the_median(self):
        e = enrich_results([art('Riz', 'A', 100), art('Riz', 'B', 100), art('Riz', 'C', 130),
                            art('Huile', 'A', 200, 'L'), art('Huile', 'B', 180, 'L'), art('Huile', 'C', 200, 'L'),
                            art('Seul', 'A', 50)])  # un seul magasin : ignoré
        idx = store_price_index(e)
        self.assertEqual(idx['C']['produits_compares'], 2)
        self.assertLess(idx['B']['indice'], idx['A']['indice'])
        self.assertLess(idx['A']['indice'], idx['C']['indice'])
        self.assertEqual(idx['A']['produits_compares'], 2)

    def test_empty_and_noncomparable(self):
        self.assertEqual(unit_stats([]), {})
        self.assertEqual(store_price_index(enrich_results([art('Pack', 'A', 100, 'lot')])), {})

    def test_home_figures_count_real_data_only(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(tmp.name, 'h.db')
        db.init_db(seed=False)
        client = appmod.app.test_client()
        with db.transaction() as c:  # uniquement des données d'exemple
            db.import_articles(c, [{'article': 'Lait', 'supermarche': 'Casino', 'prix': 118}])
        s = client.get('/api/stats').get_json()
        self.assertEqual((s['produits_reels'], s['magasins_reels'], s['dernier_releve']), (0, [], None))
        with db.transaction() as c:
            db.import_articles(c, [obs(prix=4500, date_releve='2026-10-01'), obs(supermarche='Cap Sud', prix=4700, date_releve='2026-10-03'),
                                   obs(article='RIZ parfumé 5kg', supermarche='Casino', prix=4600, date_releve='2026-09-20')])
        s = client.get('/api/stats').get_json()
        self.assertEqual((s['produits_reels'], s['magasins_reels'], s['dernier_releve']),
                         (1, ['Cap Sud', 'Carrefour', 'Casino'], '2026-10-03'))  # casse ignorée, exemple exclu

    def test_api_stats_exposes_unit_prices_and_keeps_legacy_keys(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(tmp.name, 's.db')
        db.init_db(seed=False)
        with db.transaction() as c:
            db.import_articles(c, [obs(prix=4500, date_releve=TODAY), obs(supermarche='Casino', prix=4700, date_releve=TODAY)])
        s = appmod.app.test_client().get('/api/stats').get_json()
        self.assertEqual(s['prix_unitaires']['kg']['min'], 900.0)
        self.assertIn('Carrefour', s['indice_prix_magasin'])
        self.assertEqual(s['supermarkets']['Casino']['avg_price'], 4700)  # ancienne clé conservée


if __name__ == '__main__':
    unittest.main()
