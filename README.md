# 🛒 ComparePrix

Une application web simple pour comparer les prix d'articles dans différents supermarchés.

## 🚀 Fonctionnalités

- **Recherche d'articles** : Tapez le nom d'un article pour voir ses prix
- **Comparaison de prix** : Visualisez les prix dans différents supermarchés
- **Interface moderne** : Design responsive et intuitif
- **Statistiques** : Prix minimum, maximum et moyen
- **Mise en évidence** : Le meilleur prix est automatiquement mis en évidence
- **Scraping automatique** : Récupération des données depuis Jumia Côte d'Ivoire
- **Images des produits** : Affichage des images des articles
- **Liens directs** : Accès direct aux pages produits

## 📋 Prérequis

- Python 3.10 ou supérieur
- pip (gestionnaire de paquets Python)

## 🛠️ Installation

### Option 1 : Démarrage rapide (recommandé)
```bash
python run_complete.py
```

### Option 2 : Installation manuelle

1. **Cloner ou télécharger le projet**
   ```bash
   git clone <url-du-repo>
   cd ComparePrix
   ```

2. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

3. **Scraper les données Jumia (optionnel)**
   ```bash
   python scraper_jumia.py
   ```

4. **Fusionner les données**
   ```bash
   python merge_data.py
   ```

5. **Lancer l'application**
   ```bash
   python app.py
   ```

6. **Ouvrir dans le navigateur**
   ```
   http://localhost:5000
   ```

## 📊 Structure des données

Les prix sont stockés dans une base **SQLite** (`data/compareprix.db`, créée automatiquement ; chemin modifiable via `COMPAREPRIX_DB`). `data/articles.json` n'est plus qu'une source d'amorçage. Format des articles renvoyés par l'API :

```json
[
  {
    "article": "Nom de l'article",
    "supermarche": "Nom du supermarché",
    "prix": 500,
    "unite": "kg",
    "url": "https://www.jumia.ci/produit/...",
    "image_url": "https://www.jumia.ci/images/..."
  }
]
```

### Sources de données :
- **Données manuelles** : Articles saisis manuellement
- **Jumia Côte d'Ivoire** : Scraping automatique des produits alimentaires

## 🔧 Configuration

### Ajouter de nouveaux articles

Vous pouvez modifier le fichier `data/articles.json` ou ajouter des données directement dans `app.py` dans la section `sample_data`.

### Modifier les supermarchés

Les supermarchés sont définis dans les données JSON. Vous pouvez ajouter ou modifier les supermarchés selon vos besoins.

### Scraping Jumia

Le script `scraper_jumia.py` récupère automatiquement :
- **Nom du produit** (product_name)
- **Prix en FCFA** (price)
- **Source** (store = "Jumia")
- **URL du produit** (url)
- **Image du produit** (image_url)

**Catégories scrapées :**
- Supermarché
- Alimentation
- Boissons
- Fruits & Légumes
- Viandes & Poissons
- Produits laitiers
- Épicerie

**Configuration du scraping :**
- Limite : 10 produits par page
- Pause entre requêtes : 1-3 secondes
- Pause entre pages : 2-5 secondes

## 📱 Utilisation

1. **Recherche** : Entrez le nom d'un article dans le champ de recherche
2. **Comparaison** : Cliquez sur "Comparer" ou appuyez sur Entrée
3. **Résultats** : Consultez le tableau avec les prix par supermarché
4. **Statistiques** : Regardez les statistiques en haut du tableau

## 🎨 Fonctionnalités de l'interface

- **Design responsive** : Fonctionne sur desktop et mobile
- **Recherche en temps réel** : Résultats instantanés
- **Mise en évidence** : Le meilleur prix est surligné en vert
- **Statistiques** : Prix min/max/moyen affichés
- **Gestion d'erreurs** : Messages d'erreur clairs

## 🔍 Exemples de recherche

- "Riz" → Trouve tous les types de riz
- "Huile" → Trouve tous les types d'huile
- "Pain" → Trouve tous les types de pain
- "Lait" → Trouve tous les types de lait

## 🚀 Déploiement

### Local
```bash
python app.py
```

### Production
Voir la section **🚀 Mise en production** ci-dessous (Docker ou Gunicorn). Ne pas utiliser `python app.py` en production : c'est le serveur de développement, et il n'écoute que sur `127.0.0.1` par défaut (`COMPAREPRIX_HOST` pour changer).

## 📝 API Endpoints

- `GET /` : Page d'accueil
- `POST /search` : Recherche d'articles
- `GET /api/articles` : Liste de tous les articles
- `GET /api/articles/<nom>` : Articles par nom

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
- Signaler des bugs
- Proposer des améliorations
- Ajouter de nouvelles fonctionnalités

## 📄 Licence

Ce projet est sous licence MIT.

---

**ComparePrix** - Comparez intelligemment, économisez intelligemment ! 🛒💰


## 🔐 Administration des signalements

Les routes de consultation et de modération des signalements sont protégées par un jeton Bearer. Définissez `COMPAREPRIX_ADMIN_TOKEN` dans l'environnement du serveur avec une valeur secrète suffisamment longue avant le démarrage de l'application.

Exemple PowerShell :
```powershell
$env:COMPAREPRIX_ADMIN_TOKEN = "<votre-jeton-secret>"
python app.py
```

Exemple Linux/macOS :
```bash
export COMPAREPRIX_ADMIN_TOKEN="<votre-jeton-secret>"
python app.py
```

Envoyez le jeton dans l'en-tête `Authorization: Bearer <votre-jeton-secret>` pour utiliser `GET /api/feedback` et `PUT /api/feedback/<id>`. Le formulaire public `POST /submit_feedback` reste accessible sans jeton. Ne stockez pas le jeton dans le dépôt.


## 📥 Importer de vrais relevés de prix

Chaque prix porte `date_releve`, `source` (`manuel`, `ticket`, `jumia`, `signalement`) et `statut` (`valide`, `a_verifier`). Les anciennes données sans date sont affichées comme **Exemple** ; un relevé de plus de 7 jours est signalé ⚠️.

1. Remplir une copie de `data/releve_modele.csv` (unités : `kg, g, L, cl, ml, unité, lot` ; date `AAAA-MM-JJ`).
2. Simuler : `python import_prices.py releve.csv`
3. Écrire (sauvegarde automatique de la base) : `python import_prices.py releve.csv --apply --replace-examples`

L'import est « tout ou rien » : une ligne invalide annule tout et son numéro est affiché. Les relevés s'ajoutent à l'**historique** (jamais écrasé) ; le prix affiché est le plus récent. Rejouer un import ne crée pas de doublon.

## 🗄️ Base de données et signalements

- Schéma : `store`, `product`, `price_observation` (historique), vue `current_price`, `feedback` (voir `db.py`). Aucune dépendance supplémentaire (SQLite est inclus dans Python).
- Historique d'un article : `GET /api/history/<article>?supermarche=<nom>`.
- Un signalement **approuvé** (`PUT /api/feedback/<id>`, jeton admin) crée automatiquement un relevé (`source=signalement`, `statut=valide`, date du jour), une seule fois. La réponse indique `price_applied`. Sans relevé de référence (produit/supermarché inconnus) le prix n'est pas appliqué et la raison est renvoyée.
- Limitation de débit de `POST /submit_feedback` : 10 par heure et par IP (`COMPAREPRIX_FEEDBACK_LIMIT`, `COMPAREPRIX_FEEDBACK_WINDOW`). Elle est **par processus** : avec 4 workers Gunicorn la limite effective est 4×. Derrière un proxy, configurez `ProxyFix` pour que `remote_addr` soit l'IP du client.
- Les anciens outils (`data_collection.py`, `validation_tool.py`) écrivent encore dans les JSON : lancez ensuite `python migrate_to_sqlite.py` (idempotent) pour synchroniser la base.
- Scraping puis import : `python scraper_jumia_v2.py && python merge_data.py`.
- Tests : `python -m unittest test_pricing test_db -v`.

## ⚖️ Prix unitaire et prix aberrants

- **Prix unitaire** (FCFA/kg, FCFA/L ou FCFA/unité) pour comparer des conditionnements différents. Règles, dans l'ordre :
  1. le nom contient une quantité (`Riz 5kg`, `Lait 750ml`, `Eau 6x1,5L`, `Coca 33cl x6`) → le prix est celui du **conditionnement** : prix ÷ quantité ;
  2. sinon, l'`unite` `kg/g/L/cl/ml` signifie que le prix est **déjà** rapporté à cette unité (anciennes données) ;
  3. les produits `jumia` sans quantité dans le nom n'ont **pas** de prix unitaire (l'unité y est devinée par mots-clés, donc non fiable) ; `lot` n'est pas comparable.
  Le 🏆 « meilleur prix » désigne le prix unitaire le plus bas par unité de base (kg et L sont comparés séparément).
- **Prix aberrant** ⚠️ : prix unitaire éloigné de plus de `max_deviation_percent` (20 % dans `config/collection_config.json`) de la **médiane** des magasins pour le même nom d'article, avec au moins **3 magasins** (une médiane sur 2 points ne désigne aucun « mauvais » prix). Un signal à vérifier, pas un rejet.
- **Photos de signalement** : le type est vérifié sur le **contenu** (PNG, JPEG, GIF), pas sur le nom ; l'extension enregistrée vient du contenu ; max 5 Mo ; un fichier invalide est refusé (400).
- Tests : `python -m unittest test_unit_price test_pricing test_db -v`.

## 🚀 Mise en production

### Avec Docker (recommandé)
```bash
export COMPAREPRIX_ADMIN_TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"   # à conserver dans un gestionnaire de secrets
docker compose up -d --build
curl http://127.0.0.1:8000/healthz      # {"status":"ok"}
```
L'image tourne sous un utilisateur non-root, système de fichiers en lecture seule, capacités Linux retirées. La base, les photos et les sauvegardes sont dans le volume `compareprix-data` (`/app/data`). **La base démarre vide : aucune donnée d'exemple en production**, importez vos relevés avec `docker compose exec web python import_prices.py ...` (le fichier CSV doit être dans le conteneur, p. ex. `docker compose cp releve.csv web:/app/data/`).

Le port n'est publié que sur `127.0.0.1` : placez devant un reverse-proxy **HTTPS** (Caddy, Nginx, Traefik...). Une fois derrière **un** proxy de confiance : `COMPAREPRIX_TRUSTED_PROXIES=1` (sinon la limitation de débit voit l'IP du proxy) et `COMPAREPRIX_HSTS=1` (uniquement si le site est servi en HTTPS).

### Sans Docker
```bash
pip install -r requirements.txt
COMPAREPRIX_ADMIN_TOKEN=... gunicorn -c gunicorn.conf.py app:app    # PORT (8000) et WEB_CONCURRENCY (2) modifiables
```

### Variables d'environnement
| Variable | Défaut | Rôle |
|---|---|---|
| `COMPAREPRIX_ADMIN_TOKEN` | *(vide)* | Jeton Bearer des routes d'administration ; vide = routes fermées (401) |
| `COMPAREPRIX_DB` | `data/compareprix.db` | Chemin de la base SQLite |
| `COMPAREPRIX_TRUSTED_PROXIES` | `0` | Nombre de proxys de confiance (`X-Forwarded-For` n'est lu que si > 0) |
| `COMPAREPRIX_HSTS` | `0` | `1` active `Strict-Transport-Security` (HTTPS uniquement) |
| `COMPAREPRIX_FEEDBACK_LIMIT` / `_WINDOW` | `10` / `3600` | Signalements autorisés par IP et fenêtre en secondes |
| `PORT`, `WEB_CONCURRENCY`, `GUNICORN_THREADS` | `8000`, `2`, `2` | Réglages Gunicorn |

### Sécurité en place
- **CSP à nonce** : aucun script inline sans nonce, aucun `onclick=` dans la page ; une injection HTML ne peut plus exécuter de JavaScript. Autres en-têtes : `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`.
- Dépendances à jour, **0 vulnérabilité connue** (`pip-audit`), vérifié chaque semaine par la CI ; `lxml` (inutilisé) retiré.
- `GET /healthz` : sonde de santé (Docker `HEALTHCHECK`, supervision).

### Sauvegardes
```bash
python backup_db.py                 # data/backups/, 14 dernières conservées, copie vérifiée (integrity_check)
docker compose exec web python backup_db.py
```
Planifiez-la (cron : `30 2 * * * cd /chemin && python backup_db.py >> data/backup.log 2>&1`) et **copiez les fichiers hors du serveur**. Restauration : arrêter l'application, remplacer `data/compareprix.db` par la sauvegarde, supprimer `data/compareprix.db-wal` et `-shm`, redémarrer.

### Intégration continue
`.github/workflows/ci.yml` : lint (`ruff`), tests sur Python 3.10/3.12/3.13, `pip-audit`, construction de l'image Docker et test de démarrage. `dependabot.yml` propose les mises à jour chaque semaine.
