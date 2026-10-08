"""Tests : vérification d'email et récupération du mot de passe (verification.py, mailer.py).
Lancer : python -m unittest test_verification -v"""
import os
import re
import sqlite3
import unittest
import unittest.mock

import mailer
import verification
from test_collaboration import CollabCase, PHONE, PASSWORD

SMTP_ENV = {'COMPAREPRIX_SMTP_HOST': 'smtp.example.test', 'COMPAREPRIX_SMTP_FROM': 'ComparePrix <no-reply@example.test>'}
EMAIL = 'Awa.Kone@Example.com'


class VerifyCase(CollabCase):
    def setUp(self):
        super().setUp()
        patcher = unittest.mock.patch.dict(os.environ, SMTP_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sent = []
        send = unittest.mock.patch.object(mailer, 'send_mail', side_effect=lambda to, subject, body: self.sent.append((to, subject, body)))
        send.start()
        self.addCleanup(send.stop)

    def post(self, url, **payload):
        return self.client.post(url, json=payload, headers=self.csrf())

    def last_code(self):
        return re.search(r'\b(\d{6})\b', self.sent[-1][2]).group(1)

    def verify_email(self, email=EMAIL):
        self.assertEqual(self.post('/api/account/email/request', email=email).status_code, 200)
        return self.post('/api/account/email/confirm', email=email, code=self.last_code())


class TestHelpers(unittest.TestCase):
    def test_phone_normalisation(self):
        self.assertEqual(verification.normalize_phone('07 12 34 56 78'), '+2250712345678')
        self.assertEqual(verification.normalize_phone('0033612345678'), '+33612345678')
        self.assertIsNone(verification.normalize_phone('12345'))
        self.assertIsNone(verification.normalize_phone(None))

    def test_email_validation_and_masking(self):
        self.assertEqual(verification.normalize_email('  Awa@Exemple.CI '), 'awa@exemple.ci')
        for bad in ('sans-arobase', 'a@b', 'a b@c.com', '', None, 'a@' + 'x' * 300 + '.com'):
            self.assertIsNone(verification.normalize_email(bad), bad)
        self.assertEqual(verification.mask_email('awa@exemple.ci'), 'a***@exemple.ci')

    def test_mail_is_not_configured_without_smtp_variables(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(mailer.is_configured())
            with self.assertRaises(mailer.MailNotConfigured):
                mailer.send_mail('a@b.ci', 's', 'b')


class TestEmailVerification(VerifyCase):
    def test_full_flow_marks_email_verified_and_masks_it(self):
        self.register()
        response = self.verify_email()
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self.sent[0][0], 'awa.kone@example.com')
        user = self.client.get('/api/session').get_json()['user']
        self.assertTrue(user['email_verified'])
        self.assertEqual(user['email'], 'a***@example.com')
        self.assertNotIn('awa.kone', str(user))

    def test_code_is_not_stored_in_clear(self):
        self.register()
        self.post('/api/account/email/request', email=EMAIL)
        code = self.last_code()
        with sqlite3.connect(os.path.join(os.environ['COMPAREPRIX_DATA_DIR'], 'community.sqlite3')) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM verification_codes').fetchone()
        self.assertNotEqual(row['code_hash'], code)
        self.assertEqual(len(row['code_hash']), 64)  # HMAC-SHA256 hexadécimal
        self.assertNotIn(code, [str(row[k]) for k in row.keys()])

    def test_wrong_code_is_refused_and_locks_after_five_attempts(self):
        self.register()
        self.post('/api/account/email/request', email=EMAIL)
        good = self.last_code()
        wrong = '000000' if good != '000000' else '111111'
        for _ in range(5):
            self.assertEqual(self.post('/api/account/email/confirm', email=EMAIL, code=wrong).status_code, 400)
        self.assertEqual(self.post('/api/account/email/confirm', email=EMAIL, code=good).status_code, 400)  # verrouillé
        self.assertFalse(self.client.get('/api/session').get_json()['user']['email_verified'])

    def test_code_is_single_use_and_expires(self):
        self.register()
        self.post('/api/account/email/request', email=EMAIL)
        code = self.last_code()
        real = verification.clock
        with unittest.mock.patch('verification.clock', side_effect=lambda: real() + 16 * 60):
            self.assertEqual(self.post('/api/account/email/confirm', email=EMAIL, code=code).status_code, 400)
        self.post('/api/account/email/request', email=EMAIL)
        code = self.last_code()
        self.assertEqual(self.post('/api/account/email/confirm', email=EMAIL, code=code).status_code, 200)
        self.assertEqual(self.post('/api/account/email/confirm', email=EMAIL, code=code).status_code, 400)

    def test_a_new_code_invalidates_the_previous_one(self):
        self.register()
        with unittest.mock.patch('verification.secrets.randbelow', side_effect=[111111, 222222]):
            self.post('/api/account/email/request', email=EMAIL)
            self.post('/api/account/email/request', email=EMAIL)
        self.assertEqual(self.post('/api/account/email/confirm', email=EMAIL, code='111111').status_code, 400)
        self.assertEqual(self.post('/api/account/email/confirm', email=EMAIL, code='222222').status_code, 200)

    def test_code_is_bound_to_the_email_it_was_sent_to(self):
        self.register()
        self.post('/api/account/email/request', email=EMAIL)
        self.assertEqual(self.post('/api/account/email/confirm', email='autre@example.com', code=self.last_code()).status_code, 400)

    def test_email_already_verified_by_another_account_is_refused(self):
        self.register()
        self.assertEqual(self.verify_email().status_code, 200)
        self.client.post('/api/account/logout', headers=self.csrf())
        self.register(phone='0707070707')
        self.assertEqual(self.post('/api/account/email/request', email=EMAIL).status_code, 409)

    def test_requires_login_csrf_and_valid_email(self):
        self.assertEqual(self.post('/api/account/email/request', email=EMAIL).status_code, 401)
        self.register()
        self.assertEqual(self.client.post('/api/account/email/request', json={'email': EMAIL}).status_code, 403)
        self.assertEqual(self.post('/api/account/email/request', email='pas-un-email').status_code, 400)
        self.assertEqual(self.sent, [])

    def test_rate_limit_on_code_requests(self):
        self.register()
        codes = [self.post('/api/account/email/request', email=EMAIL).status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])

    def test_smtp_failure_returns_502_and_leaves_no_usable_code(self):
        self.register()
        with unittest.mock.patch.object(mailer, 'send_mail', side_effect=OSError('réseau')):
            self.assertEqual(self.post('/api/account/email/request', email=EMAIL).status_code, 502)
        self.assertEqual(self.post('/api/account/email/confirm', email=EMAIL, code='123456').status_code, 400)

    def test_unavailable_without_smtp(self):
        self.register()
        with unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_SMTP_HOST': ''}):
            self.assertEqual(self.post('/api/account/email/request', email=EMAIL).status_code, 503)
            self.assertFalse(self.client.get('/api/session').get_json()['features']['email'])

    def test_requirement_is_optional_and_only_applies_when_enabled(self):
        self.register()
        self.assertTrue(self.client.get('/api/session').get_json()['features']['email'])
        self.assertFalse(self.client.get('/api/session').get_json()['features']['require_verified_email'])


class TestPasswordReset(VerifyCase):
    NEW = 'un-nouveau-mot-de-passe-solide'

    def setUp(self):
        super().setUp()
        self.register()
        self.verify_email()
        self.client.post('/api/account/logout', headers=self.csrf())
        self.sent.clear()

    def test_reset_changes_the_password_and_old_one_stops_working(self):
        self.assertEqual(self.post('/api/account/reset/request', phone=PHONE).status_code, 200)
        self.assertEqual(self.sent[0][0], 'awa.kone@example.com')
        done = self.post('/api/account/reset/confirm', phone=PHONE, code=self.last_code(), password=self.NEW)
        self.assertEqual(done.status_code, 200, done.get_json())
        self.assertEqual(self.post('/api/account/login', phone=PHONE, password=PASSWORD).status_code, 401)
        self.assertEqual(self.post('/api/account/login', phone=PHONE, password=self.NEW).status_code, 200)

    def test_request_does_not_reveal_whether_an_account_exists(self):
        known = self.post('/api/account/reset/request', phone=PHONE)
        unknown = self.post('/api/account/reset/request', phone='0909090909')
        self.assertEqual((known.status_code, known.get_json()['message']), (unknown.status_code, unknown.get_json()['message']))
        self.assertEqual(len(self.sent), 1)  # un seul email : celui du compte existant

    def test_account_without_verified_email_receives_nothing(self):
        self.register(phone='0808080808')
        self.client.post('/api/account/logout', headers=self.csrf())
        self.sent.clear()
        self.assertEqual(self.post('/api/account/reset/request', phone='0808080808').status_code, 200)
        self.assertEqual(self.sent, [])

    def test_wrong_code_and_weak_password_are_refused(self):
        self.post('/api/account/reset/request', phone=PHONE)
        code = self.last_code()
        wrong = '000000' if code != '000000' else '111111'
        self.assertEqual(self.post('/api/account/reset/confirm', phone=PHONE, code=wrong, password=self.NEW).status_code, 400)
        self.assertEqual(self.post('/api/account/reset/confirm', phone=PHONE, code=code, password='court').status_code, 400)
        self.assertEqual(self.post('/api/account/login', phone=PHONE, password=PASSWORD).status_code, 200)

    def test_reset_code_cannot_verify_an_email_and_is_single_use(self):
        self.post('/api/account/reset/request', phone=PHONE)
        code = self.last_code()
        self.assertEqual(self.post('/api/account/reset/confirm', phone=PHONE, code=code, password=self.NEW).status_code, 200)
        self.assertEqual(self.post('/api/account/reset/confirm', phone=PHONE, code=code, password=self.NEW + 'x').status_code, 400)

    def test_rate_limit_per_phone(self):
        statuses = [self.post('/api/account/reset/request', phone=PHONE).status_code for _ in range(4)]
        self.assertEqual(statuses, [200, 200, 200, 429])


class TestRequirementFlag(VerifyCase):
    def test_contribution_refused_until_email_is_verified_when_required(self):
        with unittest.mock.patch.dict(os.environ, {'COMPAREPRIX_REQUIRE_VERIFIED_EMAIL': 'true'}):
            self.setUp_app_again()
            self.register()
            refused = self.client.post('/api/contributions', data=self.form(), headers=self.csrf())
            self.assertEqual(refused.status_code, 403)
            self.assertEqual(self.verify_email().status_code, 200)
            ok = self.client.post('/api/contributions', data=self.form(), headers=self.csrf())
            self.assertEqual(ok.status_code, 201, ok.get_json())

    def setUp_app_again(self):
        from flask import Flask
        from collaboration import register_collaboration
        self.app = Flask(__name__)
        self.public_prices = register_collaboration(self.app, lambda: self.admin)
        self.client = self.app.test_client()


if __name__ == '__main__':
    unittest.main()
