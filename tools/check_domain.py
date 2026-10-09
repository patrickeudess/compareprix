#!/usr/bin/env python3
"""Vérifie qu'un nom de domaine est correctement relié à ComparePrix (lecture seule, bibliothèque standard).

    python tools/check_domain.py www.exemple.ci
    python tools/check_domain.py www.exemple.ci --apex          # vérifie aussi exemple.ci (redirection vers www)
    python tools/check_domain.py www.exemple.ci --alternate=compte.pythonanywhere.com   # et l'ancienne adresse

Ce que le script contrôle, dans l'ordre où les problèmes se rencontrent :
  1. le nom se résout en adresse IP (DNS) et vers quelle cible ;
  2. le certificat HTTPS est valide pour ce nom et son échéance ;
  3. http:// renvoie vers https:// ;
  4. /healthz répond ;
  5. les en-têtes de sécurité sont présents ;
  6. le cookie de session est « Secure », « HttpOnly » et « SameSite » ;
  7. l'adresse alternative (pythonanywhere.com, ou le nom sans www) renvoie vers l'adresse officielle.
Il n'envoie que des requêtes GET et ne modifie rien. Code de sortie : 0 s'il n'y a aucun échec, 1 sinon.
« AVERT. » signale un point à traiter sans bloquer. Un contrôle « SAUT » est impossible tant qu'une étape précédente échoue.
"""
import http.client
import socket
import ssl
import sys
from datetime import datetime, timezone

TIMEOUT = 15
SECURITY_HEADERS = ('content-security-policy', 'x-content-type-options', 'x-frame-options', 'referrer-policy')


class Net:
    """Accès réseau isolé pour pouvoir le simuler dans les tests."""

    def resolve(self, host):
        canonical, aliases, addresses = socket.gethostbyname_ex(host)
        return canonical, aliases, addresses

    def tls(self, host):
        """Retourne (jours_restants, émetteur) ou lève ssl.SSLError / OSError si le certificat est invalide pour ce nom."""
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=TIMEOUT) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls:
                cert = tls.getpeercert()
        expires = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert['notAfter']), tz=timezone.utc)
        issuer = dict(x[0] for x in cert.get('issuer', ()))
        return (expires - datetime.now(timezone.utc)).days, issuer.get('organizationName') or issuer.get('commonName', '?')

    def get(self, host, path, https=True, headers=None):
        """GET sans suivre les redirections. Retourne (statut, en-têtes en minuscules, liste des cookies)."""
        conn = (http.client.HTTPSConnection(host, timeout=TIMEOUT, context=ssl.create_default_context()) if https
                else http.client.HTTPConnection(host, timeout=TIMEOUT))
        try:
            conn.request('GET', path, headers={'User-Agent': 'comparprix-domaine/1', **(headers or {})})
            response = conn.getresponse()
            response.read()
            heads = {k.lower(): v for k, v in response.getheaders()}
            cookies = [v for k, v in response.getheaders() if k.lower() == 'set-cookie']
            return response.status, heads, cookies
        finally:
            conn.close()


def run(host, apex=False, alternate=None, net=None, out=print):
    """Exécute les contrôles. Retourne la liste des (niveau, nom, détail) ; niveau : OK, AVERT., ECHEC, SAUT."""
    net = net or Net()
    results = []

    def record(level, name, detail=''):
        results.append((level, name, detail))
        out(f'{level:<7} {name}' + (f'  ->  {detail}' if detail else ''))

    host = host.strip().lower().rstrip('.')
    if 'compareprix' not in host:
        record('AVERT.', 'nom du domaine', f'« {host} » ne contient pas « compareprix » : faute de frappe possible (« comparepirx » ?)')

    try:
        canonical, aliases, addresses = net.resolve(host)
        target = canonical if canonical != host else (aliases[0] if aliases else '')
        record('OK', 'DNS', f'{host} -> {", ".join(addresses)}' + (f' (via {target})' if target and target != host else ''))
        dns_ok = True
    except OSError as error:
        record('ECHEC', 'DNS', f'le nom ne se résout pas ({error}). Enregistrement CNAME absent, mal saisi ou pas encore propagé ?')
        dns_ok = False

    tls_ok = False
    if dns_ok:
        try:
            days, issuer = net.tls(host)
            if days < 0:
                record('ECHEC', 'certificat HTTPS', f'expiré depuis {-days} jour(s)')
            else:
                record('AVERT.' if days < 14 else 'OK', 'certificat HTTPS', f'valide pour ce nom, émetteur {issuer}, expire dans {days} jour(s)'
                       + (' : renouvellement à vérifier' if days < 14 else ''))
                tls_ok = True
        except (ssl.SSLError, OSError) as error:
            record('ECHEC', 'certificat HTTPS', f'{error}. Certificat absent ou émis pour un autre nom : activer Let\'s Encrypt une fois le DNS propagé.')
    else:
        record('SAUT', 'certificat HTTPS', 'DNS non résolu')

    if dns_ok:
        try:
            status, heads, _ = net.get(host, '/', https=False)
            location = heads.get('location', '')
            if status in (301, 302, 307, 308) and location.startswith(f'https://{host}'):
                record('OK', 'http -> https', f'{status} vers {location}')
            elif status in (301, 302, 307, 308) and location.startswith('https://'):
                record('AVERT.', 'http -> https', f'redirige vers un autre nom : {location}')
            else:
                record('AVERT.', 'http -> https', f'http:// répond {status} sans redirection : activer « Force HTTPS » sur PythonAnywhere')
        except OSError as error:
            record('AVERT.', 'http -> https', f'port 80 injoignable ({error})')

    if tls_ok:
        try:
            status, heads, _ = net.get(host, '/healthz')
            record('OK' if status == 200 else 'ECHEC', '/healthz', f'HTTP {status}')
            status, heads, _ = net.get(host, '/')
            missing = [h for h in SECURITY_HEADERS if h not in heads]
            record('OK' if status == 200 and not missing else 'ECHEC', 'page d\'accueil et en-têtes de sécurité',
                   f'HTTP {status}' + (f', manquants : {", ".join(missing)}' if missing else ''))
            hsts = heads.get('strict-transport-security')
            record('OK' if hsts else 'AVERT.', 'HSTS', hsts or 'absent : à activer (COMPAREPRIX_HSTS=1) UNE FOIS le HTTPS confirmé')
            status, heads, cookies = net.get(host, '/api/session')
            cookie = cookies[0] if cookies else ''
            flags = [f for f in ('Secure', 'HttpOnly', 'SameSite') if f.lower() in cookie.lower()]
            if not cookie:
                record('ECHEC', 'cookie de session', f'aucun cookie reçu (HTTP {status})')
            else:
                lacking = [f for f in ('Secure', 'HttpOnly', 'SameSite') if f not in flags]
                record('OK' if not lacking else 'ECHEC', 'cookie de session',
                       'Secure, HttpOnly, SameSite' if not lacking else f'drapeaux manquants : {", ".join(lacking)} (Secure : COMPAREPRIX_COOKIE_SECURE=true)')
        except (ssl.SSLError, OSError) as error:
            record('ECHEC', 'requêtes HTTPS', str(error))
    else:
        record('SAUT', 'santé, en-têtes et cookie', 'HTTPS indisponible')

    others = []
    if alternate:
        others.append((alternate, 'adresse alternative'))
    if apex and host.startswith('www.'):
        others.append((host[4:], 'domaine sans www'))
    for other, label in others:
        try:
            net.resolve(other)
        except OSError:
            record('AVERT.', f'{label} ({other})', 'ne se résout pas : à relier ou à rediriger chez le bureau d\'enregistrement')
            continue
        for https in (True, False):
            try:
                status, heads, _ = net.get(other, '/', https=https)
                break
            except (ssl.SSLError, OSError):
                status, heads = None, {}
        location = heads.get('location', '')
        if status in (301, 308) and location.startswith(f'https://{host}'):
            record('OK', f'{label} ({other})', f'{status} vers {location}')
        else:
            record('AVERT.', f'{label} ({other})', f'ne redirige pas vers {host} (HTTP {status}, Location={location or "aucune"})')
    failures = [r for r in results if r[0] == 'ECHEC']
    out(f'\n{len([r for r in results if r[0] == "OK"])} contrôle(s) OK, {len([r for r in results if r[0] == "AVERT."])} avertissement(s), {len(failures)} échec(s)')
    return results


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 1:
        sys.exit(__doc__)
    alternate = next((a.split('=', 1)[1] for a in argv if a.startswith('--alternate=')), None)
    results = run(args[0], apex='--apex' in argv, alternate=alternate)
    return 1 if any(level == 'ECHEC' for level, _, _ in results) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
