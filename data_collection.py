#!/usr/bin/env python3
"""
Système de collecte de données ComparePrix
Méthodes mixtes : Relevé manuel, tickets de caisse, scraping
Contrôle qualité : Validation multi-sources, détection d'incohérences
"""

import json
import os
import csv
from datetime import datetime, timedelta
import hashlib
from typing import List, Dict, Optional, Tuple
import re

class DataCollector:
    def __init__(self):
        self.data_file = 'data/articles.json'
        self.manual_data_file = 'data/manual_collection.json'
        self.receipts_file = 'data/receipts.json'
        self.validation_file = 'data/validation_log.json'
        self.quality_file = 'data/quality_metrics.json'
        
        # Créer les dossiers nécessaires
        os.makedirs('data', exist_ok=True)
        os.makedirs('data/backups', exist_ok=True)
        os.makedirs('data/receipts', exist_ok=True)
        
        # Initialiser les fichiers s'ils n'existent pas
        self._init_files()
    
    def _init_files(self):
        """Initialise les fichiers de données s'ils n'existent pas"""
        files_to_init = [
            (self.manual_data_file, []),
            (self.receipts_file, []),
            (self.validation_file, []),
            (self.quality_file, {})
        ]
        
        for file_path, default_value in files_to_init:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(default_value, f, ensure_ascii=False, indent=2)
    
    def add_manual_data(self, collector_name: str, supermarket: str, 
                       products: List[Dict]) -> Dict:
        """Ajoute des données de relevé manuel"""
        timestamp = datetime.now().isoformat()
        
        manual_entry = {
            'id': self._generate_id(),
            'collector': collector_name,
            'supermarket': supermarket,
            'timestamp': timestamp,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'products': products,
            'source': 'manual',
            'status': 'pending_validation'
        }
        
        # Charger et sauvegarder
        with open(self.manual_data_file, 'r', encoding='utf-8') as f:
            manual_data = json.load(f)
        
        manual_data.append(manual_entry)
        
        with open(self.manual_data_file, 'w', encoding='utf-8') as f:
            json.dump(manual_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Données manuelles ajoutées par {collector_name} pour {supermarket}")
        print(f"   - {len(products)} produits relevés")
        
        return {
            'status': 'success',
            'entry_id': manual_entry['id'],
            'products_count': len(products)
        }
    
    def add_receipt_data(self, user_name: str, supermarket: str, 
                        receipt_image: str, products: List[Dict]) -> Dict:
        """Ajoute des données de tickets de caisse"""
        timestamp = datetime.now().isoformat()
        
        receipt_entry = {
            'id': self._generate_id(),
            'user': user_name,
            'supermarket': supermarket,
            'receipt_image': receipt_image,
            'timestamp': timestamp,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'products': products,
            'source': 'receipt',
            'status': 'pending_validation'
        }
        
        # Charger et sauvegarder
        with open(self.receipts_file, 'r', encoding='utf-8') as f:
            receipts_data = json.load(f)
        
        receipts_data.append(receipt_entry)
        
        with open(self.receipts_file, 'w', encoding='utf-8') as f:
            json.dump(receipts_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Ticket de caisse ajouté par {user_name} pour {supermarket}")
        print(f"   - {len(products)} produits extraits")
        
        return {
            'status': 'success',
            'entry_id': receipt_entry['id'],
            'products_count': len(products)
        }
    
    def validate_data(self, entry_id: str, validator_name: str, 
                     validation_result: Dict) -> Dict:
        """Valide une entrée de données"""
        timestamp = datetime.now().isoformat()
        
        validation_entry = {
            'entry_id': entry_id,
            'validator': validator_name,
            'timestamp': timestamp,
            'result': validation_result,
            'status': 'validated'
        }
        
        # Charger et sauvegarder
        with open(self.validation_file, 'r', encoding='utf-8') as f:
            validation_logs = json.load(f)
        
        validation_logs.append(validation_entry)
        
        with open(self.validation_file, 'w', encoding='utf-8') as f:
            json.dump(validation_logs, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Validation effectuée par {validator_name}")
        print(f"   - Entrée {entry_id}: {validation_result.get('status', 'unknown')}")
        
        return {
            'status': 'success',
            'validation_id': validation_entry['entry_id']
        }
    
    def check_price_consistency(self, product_name: str, supermarket: str) -> Dict:
        """Vérifie la cohérence des prix pour un produit"""
        all_data = self._load_all_data_sources()
        
        # Filtrer les données
        product_data = []
        for source, data in all_data.items():
            for entry in data:
                if entry.get('status') == 'validated':
                    for product in entry.get('products', []):
                        if (product.get('article', '').lower() == product_name.lower() and
                            entry.get('supermarket', '').lower() == supermarket.lower()):
                            product_data.append({
                                'price': product.get('prix'),
                                'date': entry.get('date'),
                                'source': source,
                                'entry_id': entry.get('id')
                            })
        
        if len(product_data) < 2:
            return {
                'status': 'insufficient_data',
                'message': f'Données insuffisantes pour {product_name} chez {supermarket}',
                'data_points': len(product_data)
            }
        
        # Analyser la cohérence
        prices = [item['price'] for item in product_data if item['price']]
        if not prices:
            return {
                'status': 'no_prices',
                'message': f'Aucun prix trouvé pour {product_name} chez {supermarket}'
            }
        
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
        std_dev = variance ** 0.5
        
        # Détecter les incohérences
        inconsistencies = []
        for item in product_data:
            if item['price']:
                deviation = abs(item['price'] - avg_price) / avg_price
                if deviation > 0.2:  # Plus de 20% de variation
                    inconsistencies.append({
                        'entry_id': item['entry_id'],
                        'price': item['price'],
                        'deviation': deviation,
                        'date': item['date'],
                        'source': item['source']
                    })
        
        return {
            'status': 'analyzed',
            'product': product_name,
            'supermarket': supermarket,
            'data_points': len(product_data),
            'price_range': {
                'min': min_price,
                'max': max_price,
                'average': round(avg_price, 2),
                'std_deviation': round(std_dev, 2)
            },
            'inconsistencies': inconsistencies,
            'consistency_score': self._calculate_consistency_score(prices)
        }
    
    def _calculate_consistency_score(self, prices: List[float]) -> float:
        """Calcule un score de cohérence (0-100)"""
        if len(prices) < 2:
            return 0
        
        avg_price = sum(prices) / len(prices)
        deviations = [abs(p - avg_price) / avg_price for p in prices]
        avg_deviation = sum(deviations) / len(deviations)
        
        score = max(0, 100 - (avg_deviation * 100))
        return round(score, 2)
    
    def _load_all_data_sources(self) -> Dict:
        """Charge toutes les sources de données"""
        sources = {}
        
        for file_path, key in [
            (self.manual_data_file, 'manual'),
            (self.receipts_file, 'receipts'),
            (self.data_file, 'main')
        ]:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    sources[key] = json.load(f)
        
        return sources
    
    def _generate_id(self) -> str:
        """Génère un ID unique"""
        timestamp = datetime.now().isoformat()
        random_component = os.urandom(8).hex()
        return hashlib.md5(f"{timestamp}{random_component}".encode()).hexdigest()[:12]
    
    def generate_quality_report(self) -> Dict:
        """Génère un rapport de qualité des données"""
        all_data = self._load_all_data_sources()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {},
            'sources': {},
            'recommendations': []
        }
        
        # Analyser chaque source
        for source_name, data in all_data.items():
            if source_name == 'main':
                continue
            
            source_stats = {
                'total_entries': len(data),
                'validated_entries': len([e for e in data if e.get('status') == 'validated']),
                'pending_entries': len([e for e in data if e.get('status') == 'pending_validation']),
                'total_products': sum(len(e.get('products', [])) for e in data),
                'supermarkets': list(set(e.get('supermarket') for e in data if e.get('supermarket')))
            }
            
            report['sources'][source_name] = source_stats
        
        # Statistiques globales
        total_entries = sum(len(data) for source, data in all_data.items() if source != 'main')
        validated_entries = sum(
            len([e for e in data if e.get('status') == 'validated'])
            for source, data in all_data.items() if source != 'main'
        )
        
        report['summary'] = {
            'total_entries': total_entries,
            'validated_entries': validated_entries,
            'validation_rate': round((validated_entries / total_entries * 100) if total_entries > 0 else 0, 2),
            'data_sources': len([s for s in all_data.keys() if s != 'main'])
        }
        
        return report

def main():
    """Fonction principale pour tester le système de collecte"""
    collector = DataCollector()
    
    print("🛒 Système de collecte de données ComparePrix")
    print("=" * 50)
    
    # Exemple de données manuelles
    manual_products = [
        {'article': 'Riz Basmati', 'prix': 520, 'unite': 'kg'},
        {'article': 'Huile d\'Olive', 'prix': 1250, 'unite': 'L'},
        {'article': 'Pain', 'prix': 85, 'unite': 'unité'}
    ]
    
    result = collector.add_manual_data('Jean Dupont', 'Carrefour', manual_products)
    
    # Exemple de validation
    validation_result = {
        'status': 'approved',
        'notes': 'Prix cohérents avec les données existantes',
        'confidence': 0.9
    }
    
    collector.validate_data(result['entry_id'], 'Marie Martin', validation_result)
    
    # Vérifier la cohérence
    consistency = collector.check_price_consistency('Riz Basmati', 'Carrefour')
    print(f"\nCohérence des prix: {consistency}")
    
    # Générer un rapport
    report = collector.generate_quality_report()
    print(f"\nRapport de qualité: {report['summary']}")

if __name__ == "__main__":
    main()
