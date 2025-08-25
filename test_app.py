#!/usr/bin/env python3
"""
Script de test pour ComparePrix
Vérifie que l'application fonctionne correctement
"""

import json
import os
import requests
import time

def test_data_files():
    """Teste l'existence et la validité des fichiers de données"""
    print("📁 Test des fichiers de données...")
    
    files_to_check = [
        'data/articles.json',
        'data/jumia_products.json'
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"✅ {file_path}: {len(data)} articles")
            except Exception as e:
                print(f"❌ {file_path}: Erreur de lecture - {e}")
        else:
            print(f"❌ {file_path}: Fichier manquant")

def test_app_running():
    """Teste si l'application Flask fonctionne"""
    print("\n🌐 Test de l'application Flask...")
    
    try:
        # Attendre un peu pour que l'app démarre
        time.sleep(2)
        
        response = requests.get('http://localhost:5000', timeout=5)
        if response.status_code == 200:
            print("✅ Application Flask accessible")
            return True
        else:
            print(f"❌ Application Flask: Code {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Application Flask: Impossible de se connecter")
        return False
    except Exception as e:
        print(f"❌ Application Flask: Erreur - {e}")
        return False

def test_search_api():
    """Teste l'API de recherche"""
    print("\n🔍 Test de l'API de recherche...")
    
    try:
        # Test avec "Riz"
        response = requests.post('http://localhost:5000/search', 
                               data={'search_term': 'Riz'}, 
                               timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if 'results' in data:
                print(f"✅ API de recherche: {len(data['results'])} résultats pour 'Riz'")
                return True
            else:
                print("❌ API de recherche: Format de réponse incorrect")
                return False
        else:
            print(f"❌ API de recherche: Code {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API de recherche: Erreur - {e}")
        return False

def test_data_quality():
    """Teste la qualité des données"""
    print("\n📊 Test de la qualité des données...")
    
    try:
        with open('data/articles.json', 'r', encoding='utf-8') as f:
            articles = json.load(f)
        
        if not articles:
            print("❌ Aucun article trouvé")
            return False
        
        # Vérifier la structure des données
        required_fields = ['article', 'supermarche', 'prix', 'unite']
        valid_articles = 0
        
        for article in articles:
            if all(field in article for field in required_fields):
                if isinstance(article['prix'], (int, float)) and article['prix'] > 0:
                    valid_articles += 1
        
        print(f"✅ {valid_articles}/{len(articles)} articles valides")
        
        # Statistiques par supermarché
        supermarkets = {}
        for article in articles:
            supermarket = article['supermarche']
            if supermarket not in supermarkets:
                supermarkets[supermarket] = []
            supermarkets[supermarket].append(article)
        
        print("🏪 Répartition par supermarché:")
        for supermarket, products in supermarkets.items():
            avg_price = sum(p['prix'] for p in products) // len(products)
            print(f"   - {supermarket}: {len(products)} articles (prix moyen: {avg_price} FCFA)")
        
        return valid_articles > 0
        
    except Exception as e:
        print(f"❌ Erreur lors du test des données: {e}")
        return False

def main():
    print("🧪 Test de l'application ComparePrix")
    print("=" * 50)
    
    # Test des fichiers de données
    test_data_files()
    
    # Test de la qualité des données
    data_ok = test_data_quality()
    
    # Test de l'application (si elle est en cours d'exécution)
    app_ok = test_app_running()
    
    if app_ok:
        # Test de l'API
        api_ok = test_search_api()
    else:
        api_ok = False
        print("\n💡 Pour tester l'API, lancez d'abord l'application avec: python app.py")
    
    # Résumé
    print("\n📋 Résumé des tests:")
    print(f"   - Données: {'✅ OK' if data_ok else '❌ ÉCHEC'}")
    print(f"   - Application: {'✅ OK' if app_ok else '❌ ÉCHEC'}")
    print(f"   - API: {'✅ OK' if api_ok else '❌ ÉCHEC'}")
    
    if data_ok and app_ok and api_ok:
        print("\n🎉 Tous les tests sont passés avec succès!")
        print("L'application ComparePrix fonctionne correctement.")
    else:
        print("\n⚠️ Certains tests ont échoué.")
        print("Vérifiez la configuration et relancez les tests.")

if __name__ == "__main__":
    main()
