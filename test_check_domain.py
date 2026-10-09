"""Tests : outil de vérification d'un nom de domaine (tools/check_domain.py), avec un réseau simulé.
Lancer : python -m unittest test_check_domain -v"""
import os
import socket
import ssl
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
import check_domain as cd

HOST = 'www.compareprix.ci'
SEC = {'content-security-policy': "default-src 'self'", 'x-content-type-options': 'nosniff', 'x-frame-options': 'DENY',
       'referrer-policy': 'same-origin', 'strict-transport-security': 'max-age=31536000'}
COOKIE = ['session=abc; HttpOnly; Path=/; SameSite=Lax; Secure']


class FakeNet:
    def __init__(self, **kw):
        self.dns = kw.get('dns', {HOST: ('webapp-1.pythonanywhere.com', [], ['10.0.0.1']), 'compareprix.ci': ('compareprix.ci', [], ['10.0.0.2'])})
        self.tls_result = kw.get('tls', (60, "Let's Encrypt"))
        self.routes = kw.get('routes', {})

    def resolve(self, host):
        if host not in self.dns:
            raise socket.gaierror(-2, 'Name or service not known')
        return self.dns[host]

    def tls(self, host):
        if isinstance(self.tls_result, Exception):
            raise self.tls_result
        return self.tls_result

    def get(self, host, path, https=True, headers=None):
        key = (host, path, https)
        if key in self.routes:
            r = self.routes[key]
            if isinstance(r, Exception):
                raise r
            return r
        defaults = {
            (HOST, '/', False): (301, {'location': f'https://{HOST}/'}, []),
            (HOST, '/healthz', True): (200, {}, []),
            (HOST, '/', True): (200, dict(SEC), []),
            (HOST, '/api/session', True): (200, dict(SEC), COOKIE),
            ('compareprix.ci', '/', True): (301, {'location': f'https://{HOST}/'}, []),
        }
        if (host, path, https) in defaults:
            return defaults[(host, path, https)]
        raise OSError('route non simulée ' + str(key))


def run(net, host=HOST, **kw):
    lines = []
    results = cd.run(host, net=net, out=lines.append, **kw)
    return {name: (level, detail) for level, name, detail in results}, lines


class TestCheckDomain(unittest.TestCase):
    def test_correct_setup_has_no_failure_nor_warning(self):
        res, _ = run(FakeNet(), apex=True)
        self.assertEqual({lvl for lvl, _ in res.values()}, {'OK'}, res)

    def test_typo_in_the_name_is_flagged_without_blocking(self):
        net = FakeNet(dns={'www.comparepirx.ci': ('x', [], ['10.0.0.1'])})
        net.routes = {('www.comparepirx.ci', '/', False): (301, {'location': 'https://www.comparepirx.ci/'}, []),
                      ('www.comparepirx.ci', '/healthz', True): (200, {}, []),
                      ('www.comparepirx.ci', '/', True): (200, dict(SEC), []),
                      ('www.comparepirx.ci', '/api/session', True): (200, dict(SEC), COOKIE)}
        res, _ = run(net, host='www.comparepirx.ci')
        self.assertEqual(res['nom du domaine'][0], 'AVERT.')
        self.assertIn('comparepirx', res['nom du domaine'][1])

    def test_unresolved_dns_fails_and_skips_everything_that_depends_on_it(self):
        res, _ = run(FakeNet(dns={}))
        self.assertEqual(res['DNS'][0], 'ECHEC')
        self.assertEqual(res['certificat HTTPS'][0], 'SAUT')
        self.assertEqual(res['santé, en-têtes et cookie'][0], 'SAUT')

    def test_certificate_for_another_name_fails_with_the_fix(self):
        res, _ = run(FakeNet(tls=ssl.SSLCertVerificationError('hostname mismatch')))
        self.assertEqual(res['certificat HTTPS'][0], 'ECHEC')
        self.assertIn("Let's Encrypt", res['certificat HTTPS'][1])
        self.assertEqual(res['santé, en-têtes et cookie'][0], 'SAUT')

    def test_expired_and_soon_expiring_certificates(self):
        self.assertEqual(run(FakeNet(tls=(-3, 'X')))[0]['certificat HTTPS'][0], 'ECHEC')
        self.assertEqual(run(FakeNet(tls=(5, 'X')))[0]['certificat HTTPS'][0], 'AVERT.')

    def test_http_without_redirect_is_a_warning_with_the_fix(self):
        res, _ = run(FakeNet(routes={(HOST, '/', False): (200, {}, [])}))
        self.assertEqual(res['http -> https'][0], 'AVERT.')
        self.assertIn('Force HTTPS', res['http -> https'][1])

    def test_cookie_without_secure_flag_fails(self):
        res, _ = run(FakeNet(routes={(HOST, '/api/session', True): (200, dict(SEC), ['session=a; HttpOnly; SameSite=Lax'])}))
        self.assertEqual(res['cookie de session'][0], 'ECHEC')
        self.assertIn('Secure', res['cookie de session'][1])
        self.assertIn('COMPAREPRIX_COOKIE_SECURE', res['cookie de session'][1])

    def test_missing_security_headers_and_hsts_are_reported(self):
        res, _ = run(FakeNet(routes={(HOST, '/', True): (200, {}, [])}))
        self.assertEqual(res["page d'accueil et en-têtes de sécurité"][0], 'ECHEC')
        self.assertEqual(res['HSTS'][0], 'AVERT.')

    def test_unhealthy_backend_fails(self):
        res, _ = run(FakeNet(routes={(HOST, '/healthz', True): (503, {}, [])}))
        self.assertEqual(res['/healthz'][0], 'ECHEC')

    def test_apex_not_redirecting_to_www_is_a_warning(self):
        res, _ = run(FakeNet(routes={('compareprix.ci', '/', True): (200, {}, [])}), apex=True)
        self.assertEqual(res['domaine sans www (compareprix.ci)'][0], 'AVERT.')
        res, _ = run(FakeNet(dns={HOST: ('w', [], ['10.0.0.1'])}), apex=True)
        self.assertEqual(res['domaine sans www (compareprix.ci)'][0], 'AVERT.')

    def test_old_address_redirect_is_checked(self):
        alt = 'patrickeudess.pythonanywhere.com'
        net = FakeNet(dns={HOST: ('w', [], ['10.0.0.1']), alt: (alt, [], ['10.0.0.9'])},
                      routes={(alt, '/', True): (301, {'location': f'https://{HOST}/'}, [])})
        self.assertEqual(run(net, alternate=alt)[0][f'adresse alternative ({alt})'][0], 'OK')
        net.routes[(alt, '/', True)] = (200, {}, [])
        self.assertEqual(run(net, alternate=alt)[0][f'adresse alternative ({alt})'][0], 'AVERT.')

    def test_exit_code_is_1_only_when_a_check_fails(self):
        import unittest.mock as mock
        with mock.patch.object(cd, 'run', return_value=[('OK', 'a', ''), ('AVERT.', 'b', '')]):
            self.assertEqual(cd.main(['www.exemple.ci']), 0)
        with mock.patch.object(cd, 'run', return_value=[('OK', 'a', ''), ('ECHEC', 'b', '')]):
            self.assertEqual(cd.main(['www.exemple.ci']), 1)

    def test_options_are_passed_to_the_checks(self):
        import unittest.mock as mock
        with mock.patch.object(cd, 'run', return_value=[]) as fake:
            cd.main(['www.exemple.ci', '--apex', '--alternate=a.pythonanywhere.com'])
        fake.assert_called_once_with('www.exemple.ci', apex=True, alternate='a.pythonanywhere.com')


class TestRealNetworkFailureIsHandledCleanly(unittest.TestCase):
    def test_unresolvable_name_does_not_crash_with_the_real_network_layer(self):
        lines = []
        results = {name: level for level, name, _ in cd.run('nom-inexistant.invalid', out=lines.append)}
        self.assertEqual(results['DNS'], 'ECHEC')
        self.assertEqual(results['certificat HTTPS'], 'SAUT')
        self.assertTrue(lines[-1].endswith('1 échec(s)'), lines[-1])


if __name__ == '__main__':
    unittest.main()
