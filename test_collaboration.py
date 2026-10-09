"""Tests : comptes contributeurs, relevés datés, modération (collaboration.py).
Lancer : python -m unittest test_collaboration -v"""
import io
import os
import tempfile
import unittest
import unittest.mock
from datetime import date, timedelta

from flask import Flask

from collaboration import register_collaboration

PHONE, PASSWORD = '0102030405', 'un-mot-de-passe-solide'


class CollabCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_DATA_DIR': tmp.name,
                                                         'COMPAREPRIX_SECRET_KEY': 'cle-de-test'})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.admin = False
        self.app = Flask(__name__)
        self.public_prices = register_collaboration(self.app, lambda: self.admin)
        self.client = self.app.test_client()

    def csrf(self):
        return {'X-CSRF-Token': self.client.get('/api/session').get_json()['csrf']}

    def register(self, phone=PHONE, password=PASSWORD):
        return self.client.post('/api/account/register', json={'phone': phone, 'password': password, 'name': 'Awa', 'consent': True},
                                headers=self.csrf())

    def form(self, **kw):
        base = dict(article='Riz', brand='Maman', variant='', store='Carrefour', city='Abidjan', district='Cocody',
                    shop='Carrefour Cocody', quantity='5', unit='kg', price='3000', availability='available',
                    observed_at=date.today().isoformat())
        base.update(kw)
        return base

    def send(self, **kw):
        return self.client.post('/api/contributions', data=self.form(**kw), headers=self.csrf())


class TestAccounts(CollabCase):
    def test_registration_login_and_logout(self):
        r = self.register()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['user']['phone'], '+225' + PHONE)
        self.client.post('/api/account/logout', headers=self.csrf())
        self.assertIsNone(self.client.get('/api/session').get_json()['user'])
        bad = self.client.post('/api/account/login', json={'phone': PHONE, 'password': 'faux'}, headers=self.csrf())
        self.assertEqual(bad.status_code, 401)
        ok = self.client.post('/api/account/login', json={'phone': PHONE, 'password': PASSWORD}, headers=self.csrf())
        self.assertEqual(ok.status_code, 200)

    def test_weak_password_duplicate_phone_and_missing_csrf_are_refused(self):
        self.assertEqual(self.register(password='court').status_code, 400)
        self.assertEqual(self.register().status_code, 200)
        self.client.post('/api/account/logout', headers=self.csrf())
        self.assertEqual(self.register().status_code, 409)
        self.assertEqual(self.client.post('/api/account/register', json={'phone': PHONE, 'password': PASSWORD}).status_code, 403)

    def test_registration_requires_explicit_consent_but_login_does_not(self):
        for consent in (None, False, 'true', 1, 'on'):
            body = {'phone': PHONE, 'password': PASSWORD, 'name': 'Awa'}
            if consent is not None:
                body['consent'] = consent
            response = self.client.post('/api/account/register', json=body, headers=self.csrf())
            self.assertEqual(response.status_code, 400, repr(consent))
        self.assertEqual(self.register().status_code, 200)  # consent=True (aide de test)
        self.client.post('/api/account/logout', headers=self.csrf())
        login = self.client.post('/api/account/login', json={'phone': PHONE, 'password': PASSWORD}, headers=self.csrf())
        self.assertEqual(login.status_code, 200)

    def test_consent_date_is_recorded_for_new_accounts_only(self):
        import sqlite3
        self.register()
        path = os.path.join(os.environ['COMPAREPRIX_DATA_DIR'], 'community.sqlite3')
        conn = sqlite3.connect(path)
        try:
            self.assertIsNotNone(conn.execute('SELECT consent_at FROM users').fetchone()[0])
        finally:
            conn.close()

    def test_privacy_page_is_public_and_shows_the_configured_contact(self):
        page = self.client.get('/confidentialite')
        self.assertEqual(page.status_code, 200)
        text = page.get_data(as_text=True)
        for must in ('Numéro de téléphone', 'jamais affiché publiquement', 'Photos', 'Vos droits'):
            self.assertIn(must, text)
        self.assertIn('Contactez l’administrateur', text)
        with unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_CONTACT': 'donnees@exemple.ci'}):
            self.assertIn('donnees@exemple.ci', self.client.get('/confidentialite.html').get_data(as_text=True))

    def test_password_is_stored_hashed(self):
        self.register()
        import sqlite3
        conn = sqlite3.connect(os.path.join(os.environ['COMPAREPRIX_DATA_DIR'], 'community.sqlite3'))
        try:
            stored = conn.execute('SELECT password_hash FROM users').fetchone()[0]
        finally:
            conn.close()
        self.assertNotIn(PASSWORD, stored)


class TestContributionsAndModeration(CollabCase):
    def test_anonymous_cannot_contribute(self):
        self.assertEqual(self.client.post('/api/contributions', data=self.form(), headers=self.csrf()).status_code, 401)

    def test_pending_contribution_is_not_public_until_an_admin_approves_it(self):
        self.register()
        r = self.send()
        self.assertEqual(r.status_code, 201, r.get_json())
        cid = r.get_json()['id']
        self.assertEqual(self.public_prices(), [])
        # modération réservée à l'administrateur
        self.assertEqual(self.client.get('/api/admin/contributions').status_code, 401)
        self.assertEqual(self.client.post(f'/api/admin/contributions/{cid}/decision', json={'decision': 'approved'}).status_code, 401)
        self.admin = True
        self.assertEqual(self.client.post(f'/api/admin/contributions/{cid}/decision', json={'decision': 'approved'}).status_code, 200)
        (row,) = self.public_prices()
        self.assertEqual((row['supermarche'], row['prix'], row['source']), ('Carrefour', 3000, 'Contribution validée'))
        self.assertEqual((row['prix_unitaire'], row['unite_reference']), (600.0, 'kg'))  # 3000 FCFA / 5 kg
        self.assertEqual(self.client.get('/api/contributions').get_json()['points'], 10)

    def test_rejection_needs_a_reason_and_is_final(self):
        self.register()
        cid = self.send().get_json()['id']
        self.admin = True
        url = f'/api/admin/contributions/{cid}/decision'
        self.assertEqual(self.client.post(url, json={'decision': 'rejected'}).status_code, 400)
        self.assertEqual(self.client.post(url, json={'decision': 'rejected', 'note': 'Photo illisible'}).status_code, 200)
        self.assertEqual(self.client.post(url, json={'decision': 'approved'}).status_code, 409)
        self.assertEqual(self.public_prices(), [])

    def test_invalid_future_old_and_duplicate_readings_are_refused(self):
        self.register()
        today = date.today()
        self.assertEqual(self.send(price='0').status_code, 400)
        self.assertEqual(self.send(unit='tonne').status_code, 400)
        self.assertEqual(self.send(observed_at=(today + timedelta(days=1)).isoformat()).status_code, 400)
        self.assertEqual(self.send(observed_at=(today - timedelta(days=31)).isoformat()).status_code, 400)
        self.assertEqual(self.send().status_code, 201)
        self.assertEqual(self.send().status_code, 409)

    def test_non_image_proof_is_refused(self):
        self.register()
        data = {**self.form(), 'photo': (io.BytesIO(b'ceci n est pas une image'), 'preuve.jpg')}
        r = self.client.post('/api/contributions', data=data, headers=self.csrf(), content_type='multipart/form-data')
        self.assertEqual(r.status_code, 400)

    def test_price_report_requires_login_and_rejects_duplicates(self):
        report = {'article': 'Riz', 'store': 'Carrefour', 'reason': 'wrong_price', 'comment': ''}
        self.assertEqual(self.client.post('/api/reports', json=report, headers=self.csrf()).status_code, 401)
        self.register()
        self.assertEqual(self.client.post('/api/reports', json=report, headers=self.csrf()).status_code, 201)
        self.assertEqual(self.client.post('/api/reports', json=report, headers=self.csrf()).status_code, 409)
        self.assertEqual(self.client.get('/api/admin/reports').status_code, 401)
        self.admin = True
        self.assertEqual(len(self.client.get('/api/admin/reports').get_json()['reports']), 1)


if __name__ == '__main__':
    unittest.main()
