# 📋 Guide d'utilisation - Système de collecte de données ComparePrix

## 🎯 Vue d'ensemble

Le système de collecte de données ComparePrix utilise des **méthodes mixtes** pour garantir des données fiables et à jour :

1. **Relevé manuel** : Équipe de 2-3 personnes
2. **Tickets de caisse** : Via WhatsApp
3. **Scraping automatique** : Sites e-commerce

## 📊 Méthodes de collecte

### 1. 📝 Relevé manuel

#### **Équipe de collecte**
- **Taille** : 2-3 personnes
- **Fréquence** : Hebdomadaire
- **Supermarchés** : Carrefour, Cap Sud, Casino, Jumia

#### **Procédure**
1. **Préparation** : Liste des produits à relever
2. **Collecte** : Relevé des prix sur place
3. **Saisie** : Entrée des données dans le système
4. **Validation** : Contrôle par un second collecteur

#### **Produits prioritaires**
- Riz (Basmati, local)
- Huile d'olive
- Pain
- Lait
- Tomates
- Pommes
- Pâtes
- Sucre

### 2. 🧾 Tickets de caisse (WhatsApp)

#### **Intégration WhatsApp**
- **Réception** : Messages automatiques
- **Extraction** : Traitement des images
- **Validation** : Contrôle manuel

#### **Procédure utilisateur**
1. **Photo** : Prendre une photo claire du ticket
2. **Envoi** : Envoyer via WhatsApp avec mot-clé "ticket"
3. **Confirmation** : Message automatique de réception
4. **Traitement** : Extraction et validation

#### **Messages automatiques**
```
✅ Merci ! Votre ticket de caisse a été reçu.
📋 ID: R20250823120001
⏰ En cours de traitement...
```

### 3. 🤖 Scraping automatique

#### **Sources**
- **Jumia Côte d'Ivoire** : Produits alimentaires
- **Carrefour** : Prix en ligne (si disponible)

#### **Fréquence**
- **Jumia** : Quotidien
- **Carrefour** : Selon disponibilité

#### **Validation**
- **Auto-validation** : Pour les sources fiables
- **Contrôle qualité** : Détection d'anomalies

## 🔍 Contrôle qualité

### **Validation multi-sources**

#### **Règle de validation**
- **Minimum 2 sources** pour chaque prix
- **Validation manuelle** pour les incohérences
- **Score de confiance** calculé automatiquement

#### **Processus de validation**
1. **Réception** : Données collectées
2. **Vérification** : Contrôle automatique
3. **Validation** : Approbation manuelle
4. **Intégration** : Ajout à la base de données

### **Détection d'anomalies**

#### **Seuils de détection**
- **Variation > 20%** : Signalement automatique
- **Score de cohérence < 80%** : Révision requise
- **Données insuffisantes** : Collecte supplémentaire

#### **Actions correctives**
1. **Vérification** : Contrôle sur place
2. **Nouvelle collecte** : Si nécessaire
3. **Exclusion** : Données non fiables

## ⚙️ Workflow de collecte

### **Planification hebdomadaire**

#### **Lundi**
- **Planification** : Produits à relever
- **Répartition** : Supermarchés par collecteur
- **Préparation** : Matériel et listes

#### **Mardi-Jeudi**
- **Collecte** : Relevés sur place
- **Saisie** : Entrée des données
- **Validation initiale** : Premier contrôle

#### **Vendredi**
- **Validation finale** : Contrôle qualité
- **Intégration** : Mise à jour base de données
- **Rapport** : Synthèse hebdomadaire

### **Gestion des tickets WhatsApp**

#### **Réception quotidienne**
- **Monitoring** : Messages entrants
- **Traitement** : Extraction des données
- **Validation** : Contrôle qualité

#### **Suivi**
- **Statut** : En attente, validé, rejeté
- **Notifications** : Alertes automatiques
- **Rapports** : Synthèse quotidienne

## 📱 Interface de validation

### **Outil de validation**

#### **Fonctionnalités**
- **Liste des validations** : Entrées en attente
- **Validation rapide** : Approbation/rejet
- **Détection d'anomalies** : Alertes automatiques
- **Rapports** : Statistiques de qualité

#### **Utilisation**
```bash
python validation_tool.py
```

#### **Options disponibles**
1. **Voir les validations en attente**
2. **Valider une entrée**
3. **Vérifier les anomalies de prix**
4. **Générer un rapport**

### **Notifications**

#### **Types d'alertes**
- **Nouvelles données** : Collecte terminée
- **Validation requise** : Entrées en attente
- **Anomalies détectées** : Prix incohérents
- **Seuils dépassés** : Qualité insuffisante

#### **Canaux**
- **Email** : Rapports détaillés
- **WhatsApp** : Alertes urgentes
- **Interface web** : Notifications en temps réel

## 📊 Métriques de qualité

### **Indicateurs de performance**

#### **Taux de validation**
- **Objectif** : > 90%
- **Mesure** : Entrées validées / Total
- **Suivi** : Quotidien

#### **Score de cohérence**
- **Objectif** : > 80%
- **Mesure** : Cohérence des prix
- **Calcul** : Basé sur les variations

#### **Fréquence de collecte**
- **Objectif** : Hebdomadaire
- **Mesure** : Nombre de relevés
- **Suivi** : Par supermarché

### **Rapports automatiques**

#### **Rapport quotidien**
- **Nouvelles entrées** : Données collectées
- **Taux de validation** : Performance
- **Anomalies détectées** : Problèmes
- **Score de qualité** : Évaluation globale

#### **Rapport hebdomadaire**
- **Analyse des tendances** : Évolution des prix
- **Comparaison supermarchés** : Performance
- **Évolution des produits** : Changements
- **Efficacité de collecte** : Productivité

#### **Rapport mensuel**
- **Performance globale** : Vue d'ensemble
- **Améliorations qualité** : Progrès
- **Satisfaction utilisateurs** : Feedback
- **Analyse des coûts** : Rentabilité

## 🛠️ Configuration

### **Fichiers de configuration**

#### **config/collection_config.json**
```json
{
  "collection_methods": {
    "manual_collection": {
      "enabled": true,
      "team_size": 3,
      "frequency": "weekly"
    },
    "receipt_collection": {
      "enabled": true,
      "whatsapp_integration": true
    },
    "scraping": {
      "enabled": true,
      "frequency": "daily"
    }
  }
}
```

#### **config/features.json**
```json
{
  "features": {
    "dark_mode": {
      "enabled": true
    },
    "keyboard_shortcuts": {
      "enabled": true
    }
  }
}
```

### **Variables d'environnement**

#### **WhatsApp API**
```bash
WHATSAPP_API_KEY=your_api_key
WHATSAPP_PHONE_NUMBER=your_phone_number
```

#### **Notifications**
```bash
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_USERNAME=your_email
EMAIL_PASSWORD=your_password
```

## 📈 Amélioration continue

### **Optimisation du processus**

#### **Collecte manuelle**
- **Formation** : Équipe de collecte
- **Outils** : Applications mobiles
- **Automatisation** : Saisie simplifiée

#### **Tickets WhatsApp**
- **OCR** : Reconnaissance automatique
- **IA** : Extraction intelligente
- **Validation** : Contrôle automatisé

#### **Scraping**
- **Nouvelles sources** : Sites supplémentaires
- **Fréquence** : Optimisation des horaires
- **Robustesse** : Gestion des erreurs

### **Formation et support**

#### **Équipe de collecte**
- **Formation initiale** : Procédures
- **Support continu** : Questions/réponses
- **Amélioration** : Feedback et optimisation

#### **Utilisateurs WhatsApp**
- **Guide d'utilisation** : Instructions claires
- **Support technique** : Aide en cas de problème
- **Feedback** : Amélioration du service

## 🚀 Déploiement

### **Installation**

#### **Prérequis**
- Python 3.7+
- Flask
- Requests
- BeautifulSoup

#### **Installation**
```bash
pip install -r requirements.txt
python setup_collection.py
```

### **Configuration**

#### **Étape 1** : Configuration de base
```bash
python configure_collection.py
```

#### **Étape 2** : Test du système
```bash
python test_collection_system.py
```

#### **Étape 3** : Démarrage
```bash
python start_collection_service.py
```

### **Monitoring**

#### **Logs**
- **Collecte** : Activités de collecte
- **Validation** : Processus de validation
- **Erreurs** : Problèmes détectés

#### **Alertes**
- **Email** : Rapports quotidiens
- **WhatsApp** : Alertes urgentes
- **Interface** : Notifications temps réel

---

**ComparePrix** - Collecte de données fiables pour des comparaisons précises ! 🛒📊
