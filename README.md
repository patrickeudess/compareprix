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

- Python 3.7 ou supérieur
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

Les données sont stockées dans `data/articles.json` avec le format suivant :

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

### Production (avec Gunicorn)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

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
