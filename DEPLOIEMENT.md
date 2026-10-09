# Mettre ComparePrix en ligne

ComparePrix est une application **Flask** (Python + base SQLite). Elle a besoin d'un serveur qui exécute du Python et d'un
disque qui conserve la base. **GitHub Pages ne peut pas l'héberger** : il ne sert que des fichiers statiques.

## Ce que GitHub Pages peut faire : une page publique statique
Le fichier `index.html` à la racine est la **page publique** servie par GitHub Pages : elle est maintenue à part et ne dépend pas de
l'application Flask. Pour une démonstration interactive complète avec des prix fictifs (recherche, prix unitaires, prix aberrants,
sans serveur), `python tools/build_demo.py` écrit `build/demo.html` ; ce fichier n'est pas publié par défaut.

Activer Pages (une fois, après avoir fusionné la branche dans `main`) :
1. GitHub → dépôt → **Settings → Pages**.
2. *Build and deployment* → *Source* : **Deploy from a branch**.
3. *Branch* : **main**, dossier **/ (root)** → **Save**.
4. Attendre 1 à 2 minutes : `https://patrickeudess.github.io/compareprix/`.

Si la page reste vide : onglet **Actions** du dépôt, workflow « pages build and deployment » (erreur éventuelle), et vérifier que
`index.html` est bien présent sur `main`.

## Vrai hébergement (l'application complète)
Choisissez selon votre situation. **Aucune de ces procédures n'a été exécutée chez un hébergeur par moi** : elles suivent les
démarches standard et le code a été vérifié en local (voir les notes).

### A. Serveur privé virtuel (VPS) avec Docker : recommandé pour la durée
Un petit VPS Linux (Ubuntu) avec Docker. La base et les photos vont dans un volume Docker persistant.
```bash
git clone https://github.com/patrickeudess/compareprix && cd compareprix
export COMPAREPRIX_ADMIN_TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"   # à noter dans un gestionnaire de mots de passe
docker compose up -d --build
curl http://127.0.0.1:8000/healthz        # {"status":"ok"}
```
Placez ensuite un reverse-proxy HTTPS devant (Caddy est le plus simple : `compareprix.exemple.com { reverse_proxy 127.0.0.1:8000 }`),
puis ajoutez `COMPAREPRIX_TRUSTED_PROXIES=1` et `COMPAREPRIX_HSTS=1` (voir README). Sauvegardes : `docker compose exec web python backup_db.py`.
*Note : l'image Docker n'a pas pu être construite dans mon environnement (pas de démon Docker) ; la CI GitHub la construit et la teste.*

### B. PythonAnywhere (sans Docker, adapté à un premier essai)
1. Créer un compte, onglet **Files** : téléverser le dépôt (ou `git clone` dans une console *Bash*).
2. Console Bash : `mkvirtualenv --python=python3.10 cp && pip install -r requirements.txt`.
3. Onglet **Web** → *Add a new web app* → *Manual configuration* (Python 3.10) → renseigner le *virtualenv*.
4. Ouvrir le fichier WSGI indiqué par la page *Web* et le remplacer par :
   ```python
   import os, sys
   sys.path.insert(0, '/home/VOTRE_NOM/compareprix')
   os.environ['COMPAREPRIX_ADMIN_TOKEN'] = 'UN_JETON_LONG_ET_SECRET'
   os.environ['COMPAREPRIX_TRUSTED_PROXIES'] = '1'   # PythonAnywhere place un proxy devant l'application
   from wsgi import application
   ```
5. **Reload**. L'adresse est `VOTRE_NOM.pythonanywhere.com` (HTTPS fourni). Le disque est persistant, donc la base SQLite est conservée.

`COMPAREPRIX_TRUSTED_PROXIES=1` est nécessaire derrière le proxy de PythonAnywhere : sans lui, le limiteur de débit voit l'adresse du proxy et non celle du visiteur, donc tous les visiteurs partagent la même limite. Vérifiez ensuite le déploiement avec `python tools/smoke_test.py https://VOTRE_NOM.pythonanywhere.com` (lecture seule ; ajoutez `COMPAREPRIX_ADMIN_TOKEN=...` en variable d'environnement pour tester aussi l'accès admin).

Le fichier `wsgi.py` du dépôt se place dans le dossier du projet avant de charger l'application, ce qui est nécessaire car elle utilise
des chemins relatifs (testé : il fonctionne même lancé depuis un autre dossier). À vérifier chez l'hébergeur : quota de disque et
conditions de l'offre gratuite (par exemple expiration si le site n'est pas réactivé périodiquement).

### C. Hébergeurs « Docker » (Render, Fly.io, Railway...)
Possible avec le `Dockerfile` fourni, mais **à ne pas faire sans disque persistant** : sans lui, la base est effacée à chaque redémarrage.
Autre point à traiter : l'image tourne sous un utilisateur non-root, alors que ces hébergeurs montent souvent le disque avec le
propriétaire root, ce qui empêche l'écriture de la base. Je peux adapter le `Dockerfile` quand vous aurez choisi un hébergeur précis.
Les offres avec disque persistant sont généralement payantes : vérifiez la grille tarifaire en vigueur.

## Brancher votre propre nom de domaine
Voir **[docs/DOMAINE.md](docs/DOMAINE.md)** : compte payant PythonAnywhere, enregistrement CNAME `www`, HTTPS Let's Encrypt, cookies sécurisés, adresse officielle unique, HSTS, SPF/DKIM pour les emails. À vérifier à chaque étape avec `python tools/check_domain.py www.votre-domaine.ci`.

## Activer l'envoi d'email (facultatif)
Sans cela, l'application fonctionne ; seule la récupération du mot de passe est indisponible. Un fournisseur SMTP gratuit suffit (Brevo, Mailjet, Gmail avec mot de passe d'application...). Dans le fichier WSGI de PythonAnywhere, avant `from wsgi import application` :
```python
os.environ['COMPAREPRIX_SMTP_HOST'] = 'smtp-relay.brevo.com'
os.environ['COMPAREPRIX_SMTP_USER'] = 'VOTRE_IDENTIFIANT_SMTP'
os.environ['COMPAREPRIX_SMTP_PASSWORD'] = 'VOTRE_CLE_SMTP'
os.environ['COMPAREPRIX_SMTP_FROM'] = 'ComparePrix <no-reply@votre-domaine>'
```
**Compte gratuit PythonAnywhere : les connexions sortantes passent par une liste blanche de sites ; vérifier que votre fournisseur SMTP y figure, sinon l'envoi échouera (message « L'email n'a pas pu être envoyé »).** Les domaines expéditeurs doivent être authentifiés (SPF/DKIM) chez le fournisseur pour éviter le dossier spam.

## Après la mise en ligne
1. Ouvrir `/admin`, saisir le jeton, importer votre fiche de collecte remplie (`data/fiche_collecte.xlsx`, enregistrée en CSV : voir README, « Collecter les premiers prix »).
2. Configurer une sauvegarde quotidienne (`backup_db.py`, bases + photos) et la copier hors du serveur, puis une sonde sur `/healthz` : voir [docs/EXPLOITATION.md](docs/EXPLOITATION.md).
3. Vérifier `/healthz` et que `/admin` n'est joignable qu'en HTTPS.
