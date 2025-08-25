# 💬 Guide d'utilisation - Système de signalements ComparePrix

## 🎯 Vue d'ensemble

Le système de signalements permet aux utilisateurs de **communiquer directement avec l'équipe ComparePrix** pour signaler des différences de prix, des erreurs ou des observations sur le terrain.

## 👥 Pour les utilisateurs

### 📱 Comment signaler un problème

#### **Étape 1 : Rechercher un produit**
1. Allez sur http://localhost:5000
2. Recherchez le produit concerné
3. Cliquez sur le bouton **"💬 Signalement"** à côté du prix

#### **Étape 2 : Remplir le formulaire**
- **Produit** : Automatiquement rempli
- **Supermarché** : Automatiquement rempli
- **Prix actuel** : Automatiquement rempli
- **Nouveau prix observé** : **Obligatoire** - Entrez le prix que vous avez vu
- **Type de signalement** : **Obligatoire** - Choisissez le type approprié
- **Commentaire** : Optionnel - Décrivez ce que vous avez observé
- **Photo** : Optionnel - Ajoutez une photo du prix
- **Votre nom** : Optionnel - Pour le suivi
- **Email** : Optionnel - Pour les notifications

#### **Types de signalements disponibles**
- **Prix augmenté** : Le prix a augmenté par rapport à notre base
- **Prix diminué** : Le prix a baissé (promotion, etc.)
- **Prix incorrect** : Le prix affiché ne correspond pas à la réalité
- **Produit indisponible** : Le produit n'est plus disponible
- **Autre** : Autre problème ou observation

### 📸 Ajouter une photo

#### **Conseils pour une bonne photo**
- **Clarté** : Photo nette et bien éclairée
- **Prix visible** : Le prix doit être clairement lisible
- **Contexte** : Incluez le nom du produit si possible
- **Format** : JPG, PNG, GIF (max 5MB)

#### **Comment ajouter une photo**
1. Cliquez sur la zone **"📷 Cliquez pour ajouter une photo"**
2. Sélectionnez votre photo
3. Vérifiez l'aperçu
4. Si la photo est trop volumineuse, vous recevrez un message d'erreur

### ✅ Après l'envoi

#### **Confirmation**
- Message de confirmation : **"✅ Signalement envoyé avec succès !"**
- ID du signalement généré automatiquement
- Modal se ferme automatiquement après 2 secondes

#### **Suivi**
- Votre signalement est envoyé à l'équipe ComparePrix
- L'équipe examine et traite votre signalement
- Vous pouvez suivre l'évolution via votre email (si fourni)

## 👨‍💼 Pour l'équipe ComparePrix

### 🔧 Outil d'administration

#### **Accès à l'outil**
```bash
python feedback_admin.py
```

#### **Fonctionnalités disponibles**
1. **Voir tous les signalements** : Liste complète
2. **Voir les signalements en attente** : À traiter
3. **Voir les statistiques** : Analyses et métriques
4. **Traiter un signalement** : Approuver, rejeter, investiguer
5. **Exporter un rapport** : Données pour analyse

### 📊 Traitement des signalements

#### **Statuts disponibles**
- **En attente** (`pending_review`) : Nouveau signalement
- **En cours** (`in_progress`) : Investigation en cours
- **Approuvé** (`approved`) : Signalement validé
- **Rejeté** (`rejected`) : Signalement non valide

#### **Processus de traitement**
1. **Réception** : Signalement reçu automatiquement
2. **Examen** : Vérification des informations
3. **Investigation** : Contrôle sur place si nécessaire
4. **Décision** : Approuver ou rejeter
5. **Action** : Mise à jour de la base de données si approuvé

#### **Actions possibles**
- **Approuver** : Le signalement est correct, mise à jour du prix
- **Rejeter** : Le signalement est incorrect ou non pertinent
- **Investigation** : Nécessite une vérification supplémentaire

### 📈 Statistiques et rapports

#### **Métriques disponibles**
- **Total signalements** : Nombre total reçus
- **Par statut** : Répartition par état de traitement
- **Par type** : Types de signalements les plus fréquents
- **Par supermarché** : Supermarchés les plus signalés
- **Différence de prix** : Impact total des signalements

#### **Rapports automatiques**
- **Export JSON** : Données complètes
- **Statistiques** : Analyses détaillées
- **Historique** : Suivi des modifications

## 🔄 Workflow complet

### **Côté utilisateur**
```
1. Observation sur le terrain
2. Recherche du produit sur ComparePrix
3. Signalement via le bouton "💬 Signalement"
4. Remplissage du formulaire
5. Ajout de photo (optionnel)
6. Envoi du signalement
7. Confirmation de réception
```

### **Côté équipe**
```
1. Réception automatique du signalement
2. Notification à l'équipe
3. Examen des informations
4. Investigation si nécessaire
5. Décision (approuver/rejeter)
6. Mise à jour de la base de données
7. Notification à l'utilisateur (optionnel)
```

## 📁 Structure des données

### **Fichiers générés**
```
data/
├── user_feedback.json          # Signalements des utilisateurs
├── user_photos/                # Photos des signalements
│   ├── feedback_20250823_120001_photo1.jpg
│   └── feedback_20250823_120002_photo2.jpg
└── feedback_test_report.json   # Rapports de test
```

### **Structure d'un signalement**
```json
{
  "id": "fb_001_test",
  "timestamp": "2025-08-23T12:00:01",
  "date": "2025-08-23",
  "product_name": "Riz Basmati",
  "supermarket": "Carrefour",
  "current_price": 520,
  "new_price": 580,
  "price_difference": 60,
  "feedback_type": "price_increase",
  "user_comment": "Prix augmenté de 60 FCFA",
  "user_name": "Jean Dupont",
  "user_email": "jean.dupont@email.com",
  "photo_path": "data/user_photos/feedback_20250823_120001_photo.jpg",
  "status": "pending_review",
  "reviewed_by": null,
  "review_date": null,
  "review_notes": null
}
```

## 🛠️ API Endpoints

### **Soumission de signalement**
```
POST /submit_feedback
Content-Type: multipart/form-data

Paramètres:
- product_name: Nom du produit
- supermarket: Nom du supermarché
- current_price: Prix actuel
- new_price: Nouveau prix observé
- feedback_type: Type de signalement
- user_comment: Commentaire (optionnel)
- user_name: Nom utilisateur (optionnel)
- user_email: Email (optionnel)
- photo: Fichier photo (optionnel)
```

### **Récupération des signalements**
```
GET /api/feedback

Réponse:
{
  "status": "success",
  "feedback": [...]
}
```

### **Mise à jour d'un signalement**
```
PUT /api/feedback/<feedback_id>
Content-Type: application/json

{
  "status": "approved",
  "review_notes": "Prix confirmé",
  "reviewer": "Équipe ComparePrix"
}
```

## 🎯 Bonnes pratiques

### **Pour les utilisateurs**
- **Vérifiez le prix** avant de signaler
- **Prenez une photo claire** si possible
- **Décrivez précisément** ce que vous observez
- **Fournissez votre email** pour le suivi

### **Pour l'équipe**
- **Traitez rapidement** les signalements
- **Investiguez sur place** si nécessaire
- **Communiquez** avec les utilisateurs
- **Mettez à jour** la base de données

## 🚀 Déploiement

### **Configuration requise**
- Flask application running
- Dossier `data/` avec permissions d'écriture
- Espace disque pour les photos

### **Test du système**
```bash
# Test complet
python test_feedback_system.py

# Test de l'interface
python app.py
# Puis aller sur http://localhost:5000

# Administration
python feedback_admin.py
```

---

## 🎉 **Système opérationnel !**

Le système de signalements **ComparePrix** permet une **communication directe** entre utilisateurs et équipe pour maintenir des **données fiables et à jour**.

**Ensemble, nous améliorons la qualité des comparaisons de prix !** 🛒📊✨
