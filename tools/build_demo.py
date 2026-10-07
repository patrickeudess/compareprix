"""Génère la page de DÉMONSTRATION statique (GitHub Pages) : la vraie interface, un serveur simulé dans la page.

    python tools/build_demo.py                 # écrit index.html à la racine (servi par GitHub Pages)
    python tools/build_demo.py --out demo.html
    python tools/build_demo.py --fragment --out demo_fragment.html     # sans <html>/<head> (hébergeurs qui l'ajoutent)

- La page HTML est celle que rend l'application Flask (templates/index.html) : elle ne peut pas diverger.
- Le prix unitaire et la détection des prix aberrants viennent du VRAI code Python (pricing.py), exécuté ici
  sur des données FICTIVES, puis figés dans la page. Seuls les calculs liés à la date du jour sont refaits côté navigateur.
- Les 26 relevés ci-dessous sont inventés pour la démonstration ; un bandeau l'indique et la page est « noindex ».
- À relancer après toute modification de templates/index.html, pricing.py ou de ces données.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_URL = 'https://github.com/patrickeudess/compareprix'

# ===== DONNÉES FICTIVES DE DÉMONSTRATION : (article, magasin, prix, unité, jours depuis le relevé) =====
RAW=[('Riz parfumé 5kg','Carrefour',4500,'kg',1),('Riz parfumé 5kg','Cap Sud',4700,'kg',2),('Riz parfumé 5kg','Casino',7900,'kg',1),
('Riz parfumé 1kg','Casino',1100,'kg',3),('Riz brisé 5kg','Carrefour',3500,'kg',20),('Riz brisé 5kg','Cap Sud',3300,'kg',2),('Riz brisé 5kg','Casino',3450,'kg',4),
('Huile végétale 1L','Carrefour',1500,'L',1),('Huile végétale 1L','Cap Sud',1450,'L',2),('Huile végétale 1L','Casino',1520,'L',1),
('Huile végétale 5L','Carrefour',6800,'L',1),('Huile végétale 5L','Cap Sud',6600,'L',5),
('Sucre en poudre 1kg','Carrefour',800,'kg',1),('Sucre en poudre 1kg','Cap Sud',780,'kg',2),('Sucre en poudre 1kg','Casino',820,'kg',3),
('Lait UHT demi-écrémé 1L','Carrefour',900,'L',1),('Lait UHT demi-écrémé 1L','Cap Sud',930,'L',2),('Lait UHT demi-écrémé 1L','Casino',880,'L',1),
('Spaghetti 500g','Carrefour',450,'kg',2),('Spaghetti 500g','Cap Sud',420,'kg',2),('Spaghetti 500g','Casino',460,'kg',6),
('Pain baguette','Carrefour',150,'unité',1),('Pain baguette','Casino',125,'unité',1),('Pain baguette','Cap Sud',140,'unité',2),
('Tomates fraîches 1kg','Carrefour',900,'kg',1),('Tomates fraîches 1kg','Cap Sud',850,'kg',2)]


def build():
    os.environ['COMPAREPRIX_DB'] = os.path.join(tempfile.mkdtemp(), 'demo.db')  # base jetable : jamais celle de l'application
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    import db
    import app as A
    db.init_db(seed=False)
    with db.transaction() as c:  # l'import de l'application amorce des données d'exemple : on repart de zéro
        c.execute('DELETE FROM feedback')
        c.execute('DELETE FROM price_observation')
    rows = [dict(article=a, supermarche=s, prix=p, unite=u, source='manuel', statut='valide',
                 date_releve=time.strftime('%Y-%m-%d', time.localtime(time.time() - d * 86400))) for a, s, p, u, d in RAW]
    with db.transaction() as c:
        db.import_articles(c, rows)
    days = {(a, s): d for a, s, p, u, d in RAW}
    data = []
    for e in A.present(db.list_current()):
        keep = {k: e[k] for k in ('article', 'supermarche', 'prix', 'unite', 'prix_unitaire', 'unite_base',
                                  'origine_unite', 'anomalie', 'source', 'statut')}
        data.append({**keep, 'jours': days[(e['article'], e['supermarche'])]})

    client = A.app.test_client()
    page = client.get('/')
    html = page.get_data(as_text=True)
    nonce = re.search(r"nonce-([^']+)'", page.headers['Content-Security-Policy']).group(1)
    style = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    body = re.search(r'<body[^>]*>(.*)</body>', html, re.S).group(1)
    body = re.sub(r'<script nonce="[^"]*">', '<script>', body.replace(' nonce="%s"' % nonce, ''))
    return data, style, body


SHIM = r'''<script>
/* Serveur simulé : instantané des réponses réelles de l'API (prix unitaire et prix aberrants calculés par le code Python
   de l'application sur des données FICTIVES). Seuls les calculs dépendant de la date du jour sont refaits ici. */
(function () {
  const DATA = %s;
  const DAY = 86400000;
  const iso = (d) => new Date(Date.now() - d * DAY).toISOString().slice(0, 10);
  const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
  const withDates = DATA.map(a => ({ ...a, date_releve: iso(a.jours), age_jours: a.jours, fraicheur: a.jours > 7 ? 'perimee' : 'recente' }));
  const json = (obj) => new Promise(r => setTimeout(() => r(new Response(JSON.stringify(obj), { status: 200, headers: { 'Content-Type': 'application/json' } })), 150));
  function search(term) {
    const t = norm(term);
    const rows = withDates.filter(a => norm(a.article).includes(t));
    const best = {};
    rows.forEach(a => { if (a.prix_unitaire != null) best[a.unite_base] = Math.min(best[a.unite_base] ?? Infinity, a.prix_unitaire); });
    return rows.map(a => ({ ...a, meilleur_prix: a.prix_unitaire != null && a.prix_unitaire === best[a.unite_base] }))
               .sort((x, y) => norm(x.article).localeCompare(norm(y.article)) || x.prix - y.prix);
  }
  window.fetch = function (url, opts) {
    const u = typeof url === 'string' ? url : url.url;
    if (u === '/search') return json({ results: search(opts.body.get('search_term') || '') });
    if (u === '/api/stats') {
      const stores = [...new Set(withDates.map(a => a.supermarche))].sort();
      return json({ produits_reels: new Set(withDates.map(a => norm(a.article))).size, magasins_reels: stores, dernier_releve: iso(Math.min(...withDates.map(a => a.jours))) });
    }
    if (u === '/submit_feedback') return json({ status: 'success', message: 'Signalement envoyé (démonstration : rien n\'est enregistré)', feedback_id: 'demo' });
    return Promise.reject(new Error('Route non simulée : ' + u));
  };
  // alert() est ignoré par l'affichage : on affiche le message dans le bandeau
  window.alert = function (msg) {
    const n = document.getElementById('demoNote'); if (!n) return;
    n.textContent = msg; n.hidden = false; clearTimeout(window.__demoNoteT);
    window.__demoNoteT = setTimeout(() => { n.hidden = true; }, 4000);
  };
})();
</script>
'''


BANNER = '''<div class="demo-banner" role="note">
  <strong>Démonstration interactive.</strong> Les prix ci-dessous sont <strong>fictifs</strong> et il n'y a pas de serveur : les signalements ne sont pas enregistrés.
  Essayez « riz », « huile », « sucre » ou « pain ». <a href="%s">Code source</a>
  <span id="demoNote" class="demo-note" hidden></span>
</div>
''' % REPO_URL

CSS_EXTRA = '''
.demo-banner { background: #1f2937; color: #f9fafb; padding: 10px 16px; font: 500 13px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; text-align: center; }
.demo-banner strong { color: #fde68a; }
.demo-banner a { color: #bfdbfe; }
.demo-note { display: block; margin-top: 4px; color: #bfdbfe; }
'''

ICON = ('<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 100 100%27'
        '%3E%3Ctext y=%27.9em%27 font-size=%2790%27%3E%F0%9F%9B%92%3C/text%3E%3C/svg%3E">')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(ROOT, 'index.html'))
    ap.add_argument('--fragment', action='store_true', help='sans <!doctype>, <html>, <head>')
    args = ap.parse_args()
    data, style, body = build()
    shim = SHIM % json.dumps(data, ensure_ascii=False)
    i = body.rindex('<script>')  # le script de l'application est le dernier : le simulateur doit le précéder
    body = BANNER + body[:i] + shim + body[i:]
    if args.fragment:
        page = '<title>ComparePrix</title>\n<style>' + CSS_EXTRA + style + '</style>\n' + body
    else:
        page = ('<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                '<meta name="robots" content="noindex, nofollow">\n'  # prix fictifs : ne pas les faire indexer
                '<title>ComparePrix – Démonstration</title>\n' + ICON + '\n<style>' + CSS_EXTRA + style +
                '</style>\n</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    with open(args.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(page)
    print(f'✅ {args.out} ({len(page) // 1024} Ko, {len(data)} relevés fictifs)')


if __name__ == '__main__':
    main()
