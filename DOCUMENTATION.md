# 📚 Documentation Complète - ComparePrix

## 🎯 Vue d'ensemble

**ComparePrix** est une application web moderne pour comparer les prix d'articles dans différents supermarchés. L'application inclut un système de scraping automatique pour récupérer les données depuis Jumia Côte d'Ivoire.

## 📁 Structure du projet

```
ComparePrix/
├── app.py                    # Application Flask principale
├── scraper_jumia.py          # Scraper Jumia (version 1)
├── scraper_jumia_v2.py       # Scraper Jumia (version 2 - améliorée)
├── merge_data.py             # Fusion des données
├── run_complete.py           # Script de démarrage complet
├── test_app.py               # Script de test
├── requirements.txt          # Dépendances Python
├── README.md                 # Documentation utilisateur
├── DOCUMENTATION.md          # Documentation technique (ce fichier)
├── .gitignore               # Fichiers à ignorer
├── start.bat                # Script de démarrage Windows
├── start.sh                 # Script de démarrage Linux/Mac
├── templates/
│   └── index.html           # Interface utilisateur
└── data/
    ├── articles.json        # Données principales
    ├── jumia_products.json  # Données Jumia
    └── backup_*.json        # Sauvegardes
```

## 🚀 Fonctionnalités principales

### 1. **Interface utilisateur moderne**
- Design responsive (desktop + mobile)
- Interface intuitive avec dégradés et animations
- Recherche en temps réel avec AJAX
- Tableau des résultats avec mise en évidence du meilleur prix
- Statistiques automatiques (prix min/max/moyen)

### 2. **Système de scraping automatique**
- Récupération des données depuis Jumia Côte d'Ivoire
- Exploration automatique de la structure du site
- Gestion des erreurs et des timeouts
- Pauses entre requêtes pour respecter le serveur
- Conversion automatique au format ComparePrix

### 3. **Gestion des données**
- Stockage JSON avec structure flexible
- Fusion automatique des données de différentes sources
- Sauvegarde automatique avec timestamp
- Validation de la qualité des données

### 4. **API REST**
- `GET /` : Page d'accueil
- `POST /search` : Recherche d'articles
- `GET /api/articles` : Liste de tous les articles
- `GET /api/articles/<nom>` : Articles par nom

## 🔧 Architecture technique

### Backend (Flask)
```python
# Structure principale
app.py
├── Routes principales
│   ├── / (page d'accueil)
│   ├── /search (recherche)
│   └── /api/* (API REST)
├── Gestion des données
│   ├── load_articles()
│   └── save_articles()
└── Configuration
    ├── Mode debug
    └── Host 0.0.0.0:5000
```

### Frontend (HTML/CSS/JavaScript)
```html
templates/index.html
├── Design responsive
│   ├── CSS Grid/Flexbox
│   ├── Media queries
│   └── Animations CSS
├── JavaScript
│   ├── Recherche AJAX
│   ├── Affichage des résultats
│   └── Gestion des erreurs
└── Interface utilisateur
    ├── Formulaire de recherche
    ├── Tableau des résultats
    └── Statistiques
```

### Scraping (BeautifulSoup + Requests)
```python
scraper_jumia_v2.py
├── Exploration du site
│   ├── Détection des catégories
│   └── Gestion des URLs
├── Extraction des données
│   ├── Nom du produit
│   ├── Prix en FCFA
│   ├── URL du produit
│   └── Image du produit
└── Conversion des données
    ├── Format ComparePrix
    └── Détermination des unités
```

## 📊 Structure des données

### Format JSON principal
```json
{
  "article": "Nom du produit",
  "supermarche": "Nom du supermarché",
  "prix": 500,
  "unite": "kg",
  "url": "https://www.jumia.ci/produit/...",
  "image_url": "https://www.jumia.ci/images/..."
}
```

### Sources de données
1. **Données manuelles** : Articles saisis manuellement
2. **Jumia Côte d'Ivoire** : Scraping automatique
3. **Fusion automatique** : Combinaison des sources

## 🛠️ Installation et déploiement

### Démarrage rapide
```bash
python run_complete.py
```

### Installation manuelle
```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Scraper les données Jumia
python scraper_jumia_v2.py

# 3. Fusionner les données
python merge_data.py

# 4. Lancer l'application
python app.py
```

### Tests
```bash
python test_app.py
```

## 🔍 Fonctionnalités de scraping

### Catégories explorées
- Supermarché
- Alimentation
- Boissons
- Fruits & Légumes
- Viandes & Poissons
- Produits laitiers
- Épicerie

### Configuration du scraping
- **Limite** : 5 produits par page
- **Pause entre requêtes** : 1-2 secondes
- **Pause entre pages** : 2-3 secondes
- **Pause entre catégories** : 3-5 secondes
- **Timeout** : 10 secondes par requête

### Gestion des erreurs
- Détection automatique des URLs invalides
- Retry automatique en cas d'échec
- Création de données d'exemple si aucun produit trouvé
- Logs détaillés pour le debugging

## 🎨 Interface utilisateur

### Design responsive
- **Desktop** : Interface complète avec toutes les fonctionnalités
- **Mobile** : Adaptation automatique pour les petits écrans
- **Tablet** : Interface intermédiaire optimisée

### Fonctionnalités visuelles
- **Mise en évidence** : Le meilleur prix est surligné en vert
- **Images des produits** : Affichage des images avec fallback
- **Liens directs** : Boutons pour accéder aux pages produits
- **Statistiques** : Prix min/max/moyen affichés en temps réel

### Interactions utilisateur
- **Recherche** : Champ de saisie avec placeholder
- **Validation** : Messages d'erreur clairs
- **Navigation** : Support de la touche Entrée
- **Feedback** : Indicateurs de chargement

## 📈 Statistiques et métriques

### Données actuelles (exemple)
- **Total d'articles** : 23
- **Supermarchés** : 4 (Carrefour, Cap Sud, Casino, Jumia)
- **Prix moyen** : 415 FCFA
- **Articles avec images** : 2
- **Articles avec URLs** : 2

### Répartition par supermarché
- **Carrefour** : 7 articles (prix moyen: 405 FCFA)
- **Cap Sud** : 7 articles (prix moyen: 394 FCFA)
- **Casino** : 7 articles (prix moyen: 417 FCFA)
- **Jumia** : 2 articles (prix moyen: 925 FCFA)

## 🔒 Sécurité et bonnes pratiques

### Sécurité
- Validation des entrées utilisateur
- Échappement des données HTML
- Headers HTTP sécurisés
- Timeouts sur les requêtes externes

### Performance
- Limitation du nombre de requêtes
- Pauses entre les requêtes de scraping
- Cache des données en JSON
- Optimisation des requêtes AJAX

### Maintenabilité
- Code modulaire et bien documenté
- Gestion d'erreurs robuste
- Logs détaillés
- Tests automatisés

## 🚀 Améliorations futures

### Fonctionnalités prévues
1. **Scraping multi-sources** : Ajouter d'autres sites e-commerce
2. **Notifications** : Alertes de prix
3. **Historique** : Suivi des prix dans le temps
4. **Filtres avancés** : Par supermarché, gamme de prix, etc.
5. **Export** : Export des données en CSV/Excel
6. **API publique** : Documentation Swagger

### Optimisations techniques
1. **Base de données** : Migration vers PostgreSQL/MySQL
2. **Cache Redis** : Amélioration des performances
3. **Queue de tâches** : Scraping asynchrone avec Celery
4. **Docker** : Containerisation de l'application
5. **CI/CD** : Pipeline de déploiement automatique

## 📝 API Documentation

### Endpoints disponibles

#### `GET /`
Page d'accueil de l'application

#### `POST /search`
Recherche d'articles par nom

**Paramètres :**
- `search_term` (string) : Terme de recherche

**Réponse :**
```json
{
  "results": [
    {
      "article": "Riz Basmati",
      "supermarche": "Carrefour",
      "prix": 500,
      "unite": "kg",
      "url": "https://...",
      "image_url": "https://..."
    }
  ]
}
```

#### `GET /api/articles`
Liste de tous les articles

#### `GET /api/articles/<nom>`
Articles par nom spécifique

## 🤝 Contribution

### Comment contribuer
1. Fork le projet
2. Créer une branche feature
3. Implémenter les changements
4. Ajouter des tests
5. Soumettre une pull request

### Standards de code
- **Python** : PEP 8
- **JavaScript** : ESLint
- **HTML/CSS** : Prettier
- **Documentation** : Docstrings et commentaires

---

**ComparePrix** - Comparez intelligemment, économisez intelligemment ! 🛒💰
