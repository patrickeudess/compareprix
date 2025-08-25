#!/usr/bin/env python3
"""
Outil de validation manuelle pour les données collectées
Interface simple pour valider les prix et détecter les incohérences
"""

import json
import os
from datetime import datetime
from typing import Dict, List

class ValidationTool:
    def __init__(self):
        self.manual_data_file = 'data/manual_collection.json'
        self.receipts_file = 'data/receipts.json'
        self.validation_file = 'data/validation_log.json'
        self.articles_file = 'data/articles.json'
        
    def get_pending_validations(self) -> List[Dict]:
        """Récupère toutes les entrées en attente de validation"""
        pending = []
        
        # Charger les données manuelles
        if os.path.exists(self.manual_data_file):
            with open(self.manual_data_file, 'r', encoding='utf-8') as f:
                manual_data = json.load(f)
                for entry in manual_data:
                    if entry.get('status') == 'pending_validation':
                        entry['source_type'] = 'manual'
                        pending.append(entry)
        
        # Charger les tickets de caisse
        if os.path.exists(self.receipts_file):
            with open(self.receipts_file, 'r', encoding='utf-8') as f:
                receipts_data = json.load(f)
                for entry in receipts_data:
                    if entry.get('status') == 'pending_validation':
                        entry['source_type'] = 'receipt'
                        pending.append(entry)
        
        return pending
    
    def validate_entry(self, entry_id: str, validator_name: str, 
                      validation_decision: str, notes: str = "") -> Dict:
        """Valide une entrée de données"""
        try:
            # Trouver l'entrée dans les données manuelles
            if os.path.exists(self.manual_data_file):
                with open(self.manual_data_file, 'r', encoding='utf-8') as f:
                    manual_data = json.load(f)
                
                for entry in manual_data:
                    if entry.get('id') == entry_id:
                        entry['status'] = 'validated'
                        entry['validation'] = {
                            'validator': validator_name,
                            'timestamp': datetime.now().isoformat(),
                            'decision': validation_decision,
                            'notes': notes
                        }
                        
                        # Sauvegarder
                        with open(self.manual_data_file, 'w', encoding='utf-8') as f:
                            json.dump(manual_data, f, ensure_ascii=False, indent=2)
                        
                        return {'status': 'success', 'message': 'Entrée validée'}
            
            # Chercher dans les tickets de caisse
            if os.path.exists(self.receipts_file):
                with open(self.receipts_file, 'r', encoding='utf-8') as f:
                    receipts_data = json.load(f)
                
                for entry in receipts_data:
                    if entry.get('id') == entry_id:
                        entry['status'] = 'validated'
                        entry['validation'] = {
                            'validator': validator_name,
                            'timestamp': datetime.now().isoformat(),
                            'decision': validation_decision,
                            'notes': notes
                        }
                        
                        # Sauvegarder
                        with open(self.receipts_file, 'w', encoding='utf-8') as f:
                            json.dump(receipts_data, f, ensure_ascii=False, indent=2)
                        
                        return {'status': 'success', 'message': 'Ticket validé'}
            
            return {'status': 'error', 'message': 'Entrée non trouvée'}
            
        except Exception as e:
            return {'status': 'error', 'message': f'Erreur: {str(e)}'}
    
    def check_price_anomalies(self) -> List[Dict]:
        """Détecte les anomalies de prix"""
        anomalies = []
        
        # Charger les données principales
        if not os.path.exists(self.articles_file):
            return anomalies
        
        with open(self.articles_file, 'r', encoding='utf-8') as f:
            articles = json.load(f)
        
        # Grouper par produit et supermarché
        product_groups = {}
        for article in articles:
            key = (article['article'].lower(), article['supermarche'])
            if key not in product_groups:
                product_groups[key] = []
            product_groups[key].append(article)
        
        # Analyser chaque groupe
        for (product_name, supermarket), products in product_groups.items():
            if len(products) < 2:
                continue
            
            prices = [p['prix'] for p in products]
            avg_price = sum(prices) / len(prices)
            
            # Détecter les prix anormaux (> 50% de variation)
            for product in products:
                deviation = abs(product['prix'] - avg_price) / avg_price
                if deviation > 0.5:
                    anomalies.append({
                        'product': product_name,
                        'supermarket': supermarket,
                        'price': product['prix'],
                        'average_price': round(avg_price, 2),
                        'deviation': round(deviation * 100, 2),
                        'entry_id': product.get('id', 'unknown')
                    })
        
        return anomalies
    
    def generate_validation_report(self) -> Dict:
        """Génère un rapport de validation"""
        pending = self.get_pending_validations()
        anomalies = self.check_price_anomalies()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'pending_validations': len(pending),
                'price_anomalies': len(anomalies),
                'validation_rate': self._calculate_validation_rate()
            },
            'pending_entries': pending,
            'anomalies': anomalies,
            'recommendations': self._generate_recommendations(pending, anomalies)
        }
        
        return report
    
    def _calculate_validation_rate(self) -> float:
        """Calcule le taux de validation"""
        total_entries = 0
        validated_entries = 0
        
        # Compter les entrées manuelles
        if os.path.exists(self.manual_data_file):
            with open(self.manual_data_file, 'r', encoding='utf-8') as f:
                manual_data = json.load(f)
                total_entries += len(manual_data)
                validated_entries += len([e for e in manual_data if e.get('status') == 'validated'])
        
        # Compter les tickets
        if os.path.exists(self.receipts_file):
            with open(self.receipts_file, 'r', encoding='utf-8') as f:
                receipts_data = json.load(f)
                total_entries += len(receipts_data)
                validated_entries += len([e for e in receipts_data if e.get('status') == 'validated'])
        
        if total_entries == 0:
            return 0.0
        
        return round((validated_entries / total_entries) * 100, 2)
    
    def _generate_recommendations(self, pending: List, anomalies: List) -> List[str]:
        """Génère des recommandations basées sur les données"""
        recommendations = []
        
        if len(pending) > 10:
            recommendations.append("Priorité élevée: Nombreux éléments en attente de validation")
        
        if len(anomalies) > 5:
            recommendations.append("Attention: Plusieurs anomalies de prix détectées")
        
        if len(pending) == 0:
            recommendations.append("Excellent: Toutes les données sont validées")
        
        if len(anomalies) == 0:
            recommendations.append("Parfait: Aucune anomalie de prix détectée")
        
        return recommendations

def main():
    """Interface simple pour la validation"""
    tool = ValidationTool()
    
    print("🔍 Outil de validation des données ComparePrix")
    print("=" * 50)
    
    while True:
        print("\nOptions disponibles:")
        print("1. Voir les validations en attente")
        print("2. Valider une entrée")
        print("3. Vérifier les anomalies de prix")
        print("4. Générer un rapport")
        print("5. Quitter")
        
        choice = input("\nVotre choix (1-5): ").strip()
        
        if choice == '1':
            pending = tool.get_pending_validations()
            print(f"\n📋 {len(pending)} validations en attente:")
            
            for i, entry in enumerate(pending, 1):
                print(f"\n{i}. {entry['source_type'].upper()} - {entry['supermarket']}")
                print(f"   Collecteur: {entry.get('collector', entry.get('user', 'Inconnu'))}")
                print(f"   Date: {entry.get('date', 'Inconnue')}")
                print(f"   Produits: {len(entry.get('products', []))}")
                print(f"   ID: {entry['id']}")
        
        elif choice == '2':
            entry_id = input("Entrez l'ID de l'entrée à valider: ").strip()
            validator = input("Votre nom: ").strip()
            decision = input("Décision (approve/reject): ").strip()
            notes = input("Notes (optionnel): ").strip()
            
            result = tool.validate_entry(entry_id, validator, decision, notes)
            print(f"Résultat: {result['message']}")
        
        elif choice == '3':
            anomalies = tool.check_price_anomalies()
            print(f"\n⚠️ {len(anomalies)} anomalies détectées:")
            
            for anomaly in anomalies:
                print(f"\n- {anomaly['product']} chez {anomaly['supermarket']}")
                print(f"  Prix: {anomaly['price']} FCFA (moyenne: {anomaly['average_price']} FCFA)")
                print(f"  Déviation: {anomaly['deviation']}%")
        
        elif choice == '4':
            report = tool.generate_validation_report()
            print(f"\n📊 Rapport de validation:")
            print(f"   - Validations en attente: {report['summary']['pending_validations']}")
            print(f"   - Anomalies de prix: {report['summary']['price_anomalies']}")
            print(f"   - Taux de validation: {report['summary']['validation_rate']}%")
            
            if report['recommendations']:
                print(f"\n💡 Recommandations:")
                for rec in report['recommendations']:
                    print(f"   - {rec}")
        
        elif choice == '5':
            print("👋 Au revoir!")
            break
        
        else:
            print("❌ Choix invalide. Veuillez réessayer.")

if __name__ == "__main__":
    main()
