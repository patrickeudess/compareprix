"""Importe les produits scrapés (data/jumia_products.json) dans la base SQLite."""
import json
import os

import db
from pricing import validate_article


def load_json_data(filename):
    """Charge les données depuis un fichier JSON"""
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def merge_products_data(path='data/jumia_products.json'):
    """Ajoute les relevés scrapés à l'historique (les doublons exacts sont ignorés)."""
    scraped = load_json_data(path)
    valid, rejected = [], 0
    for product in scraped:
        errors = validate_article(product)
        if errors:
            rejected += 1
            print(f"⚠️ Produit ignoré ({product.get('article', '?')}): {'; '.join(errors)}")
        else:
            valid.append(product)

    db.init_db()
    with db.transaction() as conn:
        created, duplicates = db.import_articles(conn, valid)

    print(f"📊 {len(scraped)} produit(s) lus, {rejected} rejeté(s)")
    print(f"➕ {created} relevé(s) ajouté(s), {duplicates} déjà présent(s)")
    return created


def main():
    print("🔄 Import des données scrapées dans ComparePrix")
    print("=" * 40)
    merge_products_data()
    print("🎉 Terminé")


if __name__ == "__main__":
    main()
