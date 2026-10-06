"""Tests SQLite : recherche, historique, signalements, concurrence, limiteur.
Lancer : python -m unittest test_db -v"""
import atexit
import os
import tempfile
import threading
import unittest
from datetime import date

_TMP = tempfile.TemporaryDirectory()
atexit.register(_TMP.cleanup)  # nettoyage propre à la sortie
os.environ['COMPAREPRIX_DB'] = os.path.join(_TMP.name, 'boot.db')

import db
import app as appmod
from ratelimit import SlidingWindowLimiter

ADMIN = {'Authorization': 'Bearer secret-test-token'}


def article(**kw):
    base = dict(article='Pâtes Spaghetti', supermarche='Casino', prix=190, unite='kg',
                date_releve='2025-06-10', source='manuel', statut='valide')
    base.update(kw)
    return base


def feedback(fid='f1', **kw):
    base = dict(id=fid, timestamp='2025-06-12T10:00:00', date='2025-06-12', product_name='Pâtes Spaghetti',
                supermarket='Casino', current_price=190, new_price=170, price_difference=-20,
                feedback_type='price_decrease', user_comment='', user_name='Anonyme', user_email='',
                photo_path=None, status='pending_review')
    base.update(kw)
    return base


class DbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ['COMPAREPRIX_DB'] = os.path.join(self.tmp.name, 't.db')
        db.init_db(seed=False)


class TestPrices(DbCase):
    def test_accent_and_case_insensitive_search(self):
        with db.transaction() as c:
            db.add_observation(c, article())
        for term in ('pates', 'PÂTES', 'spag'):
            self.assertEqual(len(db.list_current(term)), 1, term)
        self.assertEqual(db.list_current('riz'), [])

    def test_like_wildcards_are_literal(self):
        with db.transaction() as c:
            db.add_observation(c, article())
        self.assertEqual(db.list_current('%'), [])
        self.assertEqual(db.list_current('_'), [])

    def test_latest_is_current_and_history_kept(self):
        with db.transaction() as c:
            db.add_observation(c, article(prix=200, date_releve='2025-06-01'))
            db.add_observation(c, article(prix=190, date_releve='2025-06-10'))
            db.add_observation(c, article(prix=500, date_releve='2025-05-01'))  # ancien, importé tard
        self.assertEqual(db.list_current('pates')[0]['prix'], 190)
        self.assertEqual([h['prix'] for h in db.price_history('Pâtes Spaghetti')], [190, 200, 500])

    def test_dated_survey_replaces_example(self):
        with db.transaction() as c:
            db.add_observation(c, {'article': 'Lait', 'supermarche': 'Casino', 'prix': 118})
            db.add_observation(c, article(article='Lait', prix=600))
        cur = db.list_current('lait')
        self.assertEqual((len(cur), cur[0]['prix'], cur[0]['statut']), (1, 600, 'valide'))

    def test_import_is_idempotent(self):
        with db.transaction() as c:
            first = db.import_articles(c, [article(), article(supermarche='Cap Sud')])
            again = db.import_articles(c, [article(), article(supermarche='Cap Sud')])
        self.assertEqual((first, again), ((2, 0), (0, 2)))

    def test_db_rejects_invalid_price(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            with db.transaction() as c:
                db.add_observation(c, article(prix=0))


class TestFeedbackWorkflow(DbCase):
    def setUp(self):
        super().setUp()
        with db.transaction() as c:
            db.add_observation(c, article())
        db.add_feedback(feedback())

    def test_approval_creates_price_once(self):
        r1 = db.set_feedback_status('f1', 'approved', 'ok', 'Awa')
        self.assertTrue(r1['applied'])
        cur = db.list_current('pates')[0]
        self.assertEqual((cur['prix'], cur['source'], cur['statut'], cur['date_releve']),
                         (170, 'signalement', 'valide', date.today().isoformat()))
        r2 = db.set_feedback_status('f1', 'approved')
        self.assertEqual(r2['observation_id'], r1['observation_id'])
        self.assertEqual(len(db.price_history('Pâtes Spaghetti')), 2)  # pas de doublon

    def test_reject_changes_nothing(self):
        r = db.set_feedback_status('f1', 'rejected')
        self.assertFalse(r['applied'])
        self.assertEqual(db.list_current('pates')[0]['prix'], 190)

    def test_unknown_product_not_applied_with_reason(self):
        db.add_feedback(feedback('f2', product_name='Inconnu'))
        r = db.set_feedback_status('f2', 'approved')
        self.assertFalse(r['applied'])
        self.assertIn('inconnus', r['reason'])

    def test_unknown_feedback(self):
        self.assertIsNone(db.set_feedback_status('nope', 'approved'))


class TestConcurrency(DbCase):
    def test_parallel_writes_lose_nothing(self):
        errors = []

        def work(n):
            try:
                for i in range(10):
                    db.add_feedback(feedback(f'w{n}-{i}'))
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(errors, [])
        self.assertEqual(len(db.list_feedback()), 80)


class TestLimiter(unittest.TestCase):
    def test_window(self):
        lim = SlidingWindowLimiter(2, 60)
        self.assertTrue(lim.check('a', now=0)[0])
        self.assertTrue(lim.check('a', now=1)[0])
        ok, retry = lim.check('a', now=2)
        self.assertFalse(ok)
        self.assertGreater(retry, 0)
        self.assertTrue(lim.check('b', now=2)[0])      # autre IP
        self.assertTrue(lim.check('a', now=61)[0])     # fenêtre expirée


class TestHttp(DbCase):
    def setUp(self):
        super().setUp()
        os.environ['COMPAREPRIX_ADMIN_TOKEN'] = 'secret-test-token'
        self.addCleanup(os.environ.pop, 'COMPAREPRIX_ADMIN_TOKEN', None)
        with db.transaction() as c:
            db.add_observation(c, article())
        self.client = appmod.app.test_client()
        appmod.FEEDBACK_LIMITER = SlidingWindowLimiter(3, 3600)
        self.addCleanup(setattr, appmod, 'FEEDBACK_LIMITER', appmod.FEEDBACK_LIMITER)

    def form(self, **kw):
        d = dict(product_name='Pâtes Spaghetti', supermarket='Casino', current_price='190',
                 new_price='170', feedback_type='price_decrease')
        d.update(kw)
        return d

    def test_submit_then_admin_approves_and_search_shows_new_price(self):
        r = self.client.post('/submit_feedback', data=self.form())
        self.assertEqual(r.status_code, 200)
        fid = r.get_json()['feedback_id']
        self.assertEqual(self.client.put(f'/api/feedback/{fid}', json={'status': 'approved'}).status_code, 401)
        r = self.client.put(f'/api/feedback/{fid}', json={'status': 'approved'}, headers=ADMIN)
        self.assertTrue(r.get_json()['price_applied'])
        found = self.client.post('/search', data={'search_term': 'pates'}).get_json()['results']
        self.assertEqual((found[0]['prix'], found[0]['source']), (170, 'signalement'))
        hist = self.client.get('/api/history/Pâtes Spaghetti').get_json()
        self.assertEqual(len(hist), 2)

    def test_rate_limit_returns_429(self):
        codes = [self.client.post('/submit_feedback', data=self.form()).status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])
        r = self.client.post('/submit_feedback', data=self.form())
        self.assertIn('Retry-After', r.headers)

    def test_unknown_feedback_404(self):
        r = self.client.put('/api/feedback/nope', json={'status': 'approved'}, headers=ADMIN)
        self.assertEqual(r.status_code, 404)


if __name__ == '__main__':
    unittest.main()
