#!/usr/bin/env python3
"""Vérification rapide d'un ComparePrix déployé (lecture seule, bibliothèque standard uniquement).

    python smoke_test.py https://patrickeudess.pythonanywhere.com
    COMPAREPRIX_ADMIN_TOKEN=... python smoke_test.py https://patrickeudess.pythonanywhere.com   # + contrôles admin

Ce que le script fait : des requêtes GET, plus un POST sur /search (qui ne fait que lire). Il n'écrit rien, ne supprime rien,
n'envoie aucun signalement. Le jeton admin (facultatif) se passe par variable d'environnement, jamais en argument,
pour ne pas rester dans l'historique du terminal ; il n'est envoyé qu'en en-tête, vers l'adresse que vous indiquez.
Code de sortie : 0 si tout est bon, 1 si au moins un contrôle échoue.
"""
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 25


def call(base, path, method='GET', data=None, headers=None):
    req = urllib.request.Request(base + path, method=method, headers={'User-Agent': 'comparprix-smoke/1', **(headers or {})},
                                 data=urllib.parse.urlencode(data).encode() if data else None)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def main():
    if len(sys.argv) != 2 or not sys.argv[1].startswith(('http://', 'https://')):
        sys.exit(__doc__)
    base = sys.argv[1].rstrip('/')
    token = os.environ.get('COMPAREPRIX_ADMIN_TOKEN', '')
    results = []

    def check(name, cond, detail=''):
        results.append(bool(cond))
        print(('✅' if cond else '❌'), name, ('— ' + str(detail)) if detail else '')

    def info(name, detail):
        print('ℹ️ ', name, '—', detail)

    # --- page d'accueil et en-têtes de sécurité
    try:
        status, h, body = call(base, '/')
    except Exception as e:  # réseau, TLS, DNS...
        print('❌ Impossible de joindre', base, '—', e)
        sys.exit(1)
    h = {k.lower(): v for k, v in h.items()}
    html = body.decode('utf-8', 'replace')
    check('1 page d\'accueil répond 200 en HTML', status == 200 and '<html' in html.lower(), f'HTTP {status}, {len(body)} octets')
    check('2 la page contient l\'interface ComparePrix', 'ComparePrix' in html)
    csp = h.get('content-security-policy', '')
    check('3 en-tête CSP présent, sans script inline non protégé', "script-src" in csp and "'unsafe-inline'" not in csp.split('script-src')[-1].split(';')[0], csp[:90])
    check('4 en-têtes X-Content-Type-Options / X-Frame-Options', h.get('x-content-type-options') == 'nosniff' and h.get('x-frame-options') == 'DENY')
    if base.startswith('https://'):
        info('HSTS', 'actif' if 'strict-transport-security' in h else 'absent (facultatif : COMPAREPRIX_HSTS=1 une fois le HTTPS confirmé)')
    else:
        info('HTTPS', 'adresse en http:// : à éviter pour /admin (le jeton circule en clair)')

    # --- sonde de santé et API publique
    status, _, body = call(base, '/healthz')
    check('5 /healthz répond {"status":"ok"}', status == 200 and b'"ok"' in body, f'HTTP {status}')
    status, _, body = call(base, '/search', 'POST', {'search_term': 'riz'})
    try:
        results_list = json.loads(body).get('results')
    except Exception:
        results_list = None
    check('6 recherche « riz » : réponse JSON valide', status == 200 and isinstance(results_list, list), f'HTTP {status}, {len(results_list or [])} résultat(s)')
    if results_list:
        r0 = results_list[0]
        check('7 chaque résultat porte prix, magasin, fraîcheur, prix unitaire', all(k in r0 for k in ('prix', 'supermarche', 'fraicheur', 'prix_unitaire')), sorted(r0)[:6])
    status, _, body = call(base, '/api/stats')
    try:
        stats = json.loads(body)
    except Exception:
        stats = {}
    check('8 /api/stats répond', status == 200, f'HTTP {status}')
    if 'total_articles' in stats:
        ex, tot = stats.get('donnees_exemple', 0), stats.get('total_articles', 0)
        info('données', f'{tot} relevé(s) dont {ex} d\'exemple ; {stats.get("produits_reels", 0)} produit(s) réel(s), magasins réels : {stats.get("magasins_reels")}')
    status, _, body = call(base, '/api/articles')
    check('9 /api/articles répond', status == 200)

    # --- administration : doit être fermée sans jeton
    status, _, _ = call(base, '/admin')
    check('10 page /admin servie (coquille sans donnée)', status == 200)
    for path in ('/api/feedback', '/api/observations'):
        status, _, _ = call(base, path)
        check(f'11 {path} REFUSÉ sans jeton (401)', status == 401, f'HTTP {status}')
    status, _, _ = call(base, '/api/feedback', headers={'Authorization': 'Bearer jeton-invalide-test'})
    check('12 jeton invalide refusé (401 ou 429)', status in (401, 429), f'HTTP {status}')
    if token:
        status, _, body = call(base, '/api/observations?limit=1', headers={'Authorization': 'Bearer ' + token})
        check('13 votre jeton admin est accepté', status == 200, f'HTTP {status}')
        if status == 401:
            info('jeton', 'refusé : COMPAREPRIX_ADMIN_TOKEN n\'est probablement pas défini (ou différent) côté serveur')
    else:
        info('administration', 'jeton non fourni : contrôle d\'accès admin non testé avec votre jeton')

    print('\nRÉSUMÉ :', sum(results), 'réussi(s) sur', len(results))
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
