import json
import os
from datetime import datetime

def load_json_data(filename):
    """Charge les données depuis un fichier JSON"""
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_json_data(data, filename):
    """Sauvegarde les données dans un fichier JSON"""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Données sauvegardées dans {filename}")

def merge_products_data():
    """Fusionne les données des produits de différentes sources"""
    
    # Charger les données existantes
    existing_data = load_json_data('data/articles.json')
    jumia_data = load_json_data('data/jumia_products.json')
    
    print(f"📊 Données chargées:")
    print(f"   - Données existantes: {len(existing_data)} articles")
    print(f"   - Données Jumia: {len(jumia_data)} articles")
    
    # Fusionner les données
    merged_data = existing_data.copy()
    
    # Ajouter les données Jumia
    for jumia_product in jumia_data:
        # Vérifier si le produit existe déjà (même nom et supermarché)
        existing_product = None
        for existing in merged_data:
            if (existing['article'].lower() == jumia_product['article'].lower() and 
                existing['supermarche'] == jumia_product['supermarche']):
                existing_product = existing
                break
        
        if existing_product:
            # Mettre à jour le prix si nécessaire
            if jumia_product['prix'] != existing_product['prix']:
                print(f"🔄 Mise à jour du prix pour {jumia_product['article']}: {existing_product['prix']} → {jumia_product['prix']} FCFA")
                existing_product['prix'] = jumia_product['prix']
                for champ in ('date_releve', 'source', 'statut'):
                    existing_product[champ] = jumia_product.get(champ, existing_product.get(champ))
                existing_product['url'] = jumia_product.get('url', existing_product.get('url', ''))
                existing_product['image_url'] = jumia_product.get('image_url', existing_product.get('image_url', ''))
        else:
            # Ajouter le nouveau produit
            merged_data.append(jumia_product)
            print(f"➕ Nouveau produit ajouté: {jumia_product['article']} - {jumia_product['prix']} FCFA")
    
    # Sauvegarder les données fusionnées
    save_json_data(merged_data, 'data/articles.json')
    
    # Créer une sauvegarde avec timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f'data/backup_articles_{timestamp}.json'
    save_json_data(existing_data, backup_filename)
    
    print(f"\n📈 Résumé de la fusion:")
    print(f"   - Total après fusion: {len(merged_data)} articles")
    print(f"   - Nouveaux produits ajoutés: {len(merged_data) - len(existing_data)}")
    print(f"   - Sauvegarde créée: {backup_filename}")
    
    # Afficher les statistiques par supermarché
    supermarkets = {}
    for product in merged_data:
        supermarket = product['supermarche']
        if supermarket not in supermarkets:
            supermarkets[supermarket] = []
        supermarkets[supermarket].append(product)
    
    print(f"\n🏪 Répartition par supermarché:")
    for supermarket, products in supermarkets.items():
        avg_price = sum(p['prix'] for p in products) // len(products)
        print(f"   - {supermarket}: {len(products)} articles (prix moyen: {avg_price} FCFA)")
    
    return merged_data

def main():
    print("🔄 Fusion des données ComparePrix")
    print("=" * 40)
    
    # Vérifier si les données existent
    if not os.path.exists('data/articles.json'):
        save_json_data([], 'data/articles.json')
    
    # Fusionner les données
    merged_data = merge_products_data()
    
    print(f"\n🎉 Fusion terminée avec succès!")
    print(f"L'application ComparePrix utilise maintenant {len(merged_data)} articles")

if __name__ == "__main__":
    main()
