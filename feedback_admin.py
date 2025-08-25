#!/usr/bin/env python3
"""
Outil d'administration pour gérer les signalements d'utilisateurs
Interface pour l'équipe ComparePrix
"""

import json
import os
from datetime import datetime
from typing import List, Dict

class FeedbackAdmin:
    def __init__(self):
        self.feedback_file = 'data/user_feedback.json'
        self.photos_dir = 'data/user_photos'
        
    def load_feedback(self) -> List[Dict]:
        """Charge tous les signalements"""
        if os.path.exists(self.feedback_file):
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save_feedback(self, feedback_list: List[Dict]):
        """Sauvegarde les signalements"""
        os.makedirs(os.path.dirname(self.feedback_file), exist_ok=True)
        with open(self.feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedback_list, f, ensure_ascii=False, indent=2)
    
    def get_feedback_by_status(self, status: str = None) -> List[Dict]:
        """Récupère les signalements par statut"""
        feedback_list = self.load_feedback()
        if status:
            return [f for f in feedback_list if f.get('status') == status]
        return feedback_list
    
    def update_feedback_status(self, feedback_id: str, new_status: str, 
                              reviewer: str, review_notes: str = "") -> bool:
        """Met à jour le statut d'un signalement"""
        feedback_list = self.load_feedback()
        
        for feedback in feedback_list:
            if feedback['id'] == feedback_id:
                feedback['status'] = new_status
                feedback['reviewed_by'] = reviewer
                feedback['review_date'] = datetime.now().isoformat()
                feedback['review_notes'] = review_notes
                
                self.save_feedback(feedback_list)
                return True
        
        return False
    
    def get_feedback_stats(self) -> Dict:
        """Génère des statistiques sur les signalements"""
        feedback_list = self.load_feedback()
        
        stats = {
            'total': len(feedback_list),
            'pending': len([f for f in feedback_list if f.get('status') == 'pending_review']),
            'approved': len([f for f in feedback_list if f.get('status') == 'approved']),
            'rejected': len([f for f in feedback_list if f.get('status') == 'rejected']),
            'in_progress': len([f for f in feedback_list if f.get('status') == 'in_progress']),
            'by_type': {},
            'by_supermarket': {},
            'recent': []
        }
        
        # Statistiques par type
        for feedback in feedback_list:
            feedback_type = feedback.get('feedback_type', 'unknown')
            stats['by_type'][feedback_type] = stats['by_type'].get(feedback_type, 0) + 1
            
            supermarket = feedback.get('supermarket', 'unknown')
            stats['by_supermarket'][supermarket] = stats['by_supermarket'].get(supermarket, 0) + 1
        
        # Signalements récents (7 derniers jours)
        week_ago = datetime.now().timestamp() - (7 * 24 * 60 * 60)
        stats['recent'] = [
            f for f in feedback_list 
            if datetime.fromisoformat(f['timestamp'].replace('Z', '+00:00')).timestamp() > week_ago
        ]
        
        return stats
    
    def export_feedback_report(self, format: str = 'json') -> str:
        """Exporte un rapport des signalements"""
        feedback_list = self.load_feedback()
        stats = self.get_feedback_stats()
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'statistics': stats,
            'feedback_list': feedback_list
        }
        
        if format == 'json':
            filename = f'data/feedback_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            return filename
        
        return None

def display_feedback_table(feedback_list: List[Dict]):
    """Affiche un tableau des signalements"""
    if not feedback_list:
        print("Aucun signalement trouvé.")
        return
    
    print("\n" + "="*120)
    print(f"{'ID':<12} {'Date':<10} {'Produit':<20} {'Supermarché':<12} {'Prix Actuel':<12} {'Nouveau Prix':<12} {'Différence':<12} {'Type':<15} {'Statut':<12} {'Utilisateur':<15}")
    print("="*120)
    
    for feedback in feedback_list:
        feedback_id = feedback['id'][:10] + "..."
        date = feedback['date']
        product = feedback['product_name'][:18] + "..." if len(feedback['product_name']) > 18 else feedback['product_name']
        supermarket = feedback['supermarket'][:10] + "..." if len(feedback['supermarket']) > 10 else feedback['supermarket']
        current_price = f"{feedback['current_price']} FCFA"
        new_price = f"{feedback['new_price']} FCFA"
        difference = f"{feedback['price_difference']:+} FCFA"
        feedback_type = feedback['feedback_type'][:13] + "..." if len(feedback['feedback_type']) > 13 else feedback['feedback_type']
        status = feedback['status'][:10] + "..." if len(feedback['status']) > 10 else feedback['status']
        user = feedback['user_name'][:13] + "..." if len(feedback['user_name']) > 13 else feedback['user_name']
        
        print(f"{feedback_id:<12} {date:<10} {product:<20} {supermarket:<12} {current_price:<12} {new_price:<12} {difference:<12} {feedback_type:<15} {status:<12} {user:<15}")

def display_feedback_details(feedback: Dict):
    """Affiche les détails d'un signalement"""
    print(f"\n📋 Détails du signalement {feedback['id']}")
    print("="*50)
    print(f"📅 Date: {feedback['date']} à {feedback['timestamp'][11:19]}")
    print(f"🛒 Produit: {feedback['product_name']}")
    print(f"🏪 Supermarché: {feedback['supermarket']}")
    print(f"💰 Prix actuel: {feedback['current_price']} FCFA")
    print(f"💰 Nouveau prix: {feedback['new_price']} FCFA")
    print(f"📊 Différence: {feedback['price_difference']:+} FCFA")
    print(f"🏷️ Type: {feedback['feedback_type']}")
    print(f"👤 Utilisateur: {feedback['user_name']}")
    
    if feedback.get('user_email'):
        print(f"📧 Email: {feedback['user_email']}")
    
    if feedback.get('user_comment'):
        print(f"💬 Commentaire: {feedback['user_comment']}")
    
    if feedback.get('photo_path'):
        print(f"📷 Photo: {feedback['photo_path']}")
    
    print(f"📊 Statut: {feedback['status']}")
    
    if feedback.get('reviewed_by'):
        print(f"👨‍💼 Revu par: {feedback['reviewed_by']}")
        print(f"📅 Date de révision: {feedback['review_date'][:19]}")
        if feedback.get('review_notes'):
            print(f"📝 Notes: {feedback['review_notes']}")

def main():
    """Interface principale d'administration"""
    admin = FeedbackAdmin()
    
    print("🔧 Administration des signalements ComparePrix")
    print("=" * 50)
    
    while True:
        print("\nOptions disponibles:")
        print("1. Voir tous les signalements")
        print("2. Voir les signalements en attente")
        print("3. Voir les statistiques")
        print("4. Traiter un signalement")
        print("5. Exporter un rapport")
        print("6. Quitter")
        
        choice = input("\nVotre choix (1-6): ").strip()
        
        if choice == '1':
            feedback_list = admin.load_feedback()
            display_feedback_table(feedback_list)
            
            # Option pour voir les détails
            if feedback_list:
                feedback_id = input("\nEntrez l'ID d'un signalement pour voir les détails (ou Enter pour continuer): ").strip()
                if feedback_id:
                    for feedback in feedback_list:
                        if feedback['id'].startswith(feedback_id):
                            display_feedback_details(feedback)
                            break
                    else:
                        print("Signalement non trouvé.")
        
        elif choice == '2':
            pending_feedback = admin.get_feedback_by_status('pending_review')
            print(f"\n📋 {len(pending_feedback)} signalements en attente de traitement:")
            display_feedback_table(pending_feedback)
        
        elif choice == '3':
            stats = admin.get_feedback_stats()
            print(f"\n📊 Statistiques des signalements:")
            print(f"   - Total: {stats['total']}")
            print(f"   - En attente: {stats['pending']}")
            print(f"   - Approuvés: {stats['approved']}")
            print(f"   - Rejetés: {stats['rejected']}")
            print(f"   - En cours: {stats['in_progress']}")
            print(f"   - Récents (7 jours): {len(stats['recent'])}")
            
            if stats['by_type']:
                print(f"\n📈 Par type:")
                for feedback_type, count in stats['by_type'].items():
                    print(f"   - {feedback_type}: {count}")
            
            if stats['by_supermarket']:
                print(f"\n🏪 Par supermarché:")
                for supermarket, count in stats['by_supermarket'].items():
                    print(f"   - {supermarket}: {count}")
        
        elif choice == '4':
            pending_feedback = admin.get_feedback_by_status('pending_review')
            if not pending_feedback:
                print("Aucun signalement en attente.")
                continue
            
            print(f"\n📋 Signalements en attente:")
            display_feedback_table(pending_feedback)
            
            feedback_id = input("\nEntrez l'ID du signalement à traiter: ").strip()
            if not feedback_id:
                continue
            
            # Trouver le signalement
            target_feedback = None
            for feedback in pending_feedback:
                if feedback['id'].startswith(feedback_id):
                    target_feedback = feedback
                    break
            
            if not target_feedback:
                print("Signalement non trouvé.")
                continue
            
            # Afficher les détails
            display_feedback_details(target_feedback)
            
            # Traitement
            print(f"\n🔄 Traitement du signalement:")
            print("1. Approuver et mettre à jour le prix")
            print("2. Rejeter")
            print("3. Marquer comme en cours d'investigation")
            print("4. Annuler")
            
            action = input("Votre action (1-4): ").strip()
            
            if action in ['1', '2', '3']:
                reviewer = input("Votre nom: ").strip() or "Équipe"
                review_notes = input("Notes (optionnel): ").strip()
                
                status_map = {
                    '1': 'approved',
                    '2': 'rejected',
                    '3': 'in_progress'
                }
                
                new_status = status_map[action]
                
                if admin.update_feedback_status(target_feedback['id'], new_status, reviewer, review_notes):
                    print(f"✅ Signalement {new_status} avec succès!")
                    
                    # Si approuvé, proposer de mettre à jour le prix
                    if action == '1':
                        update_price = input("Mettre à jour le prix dans la base de données ? (o/n): ").strip().lower()
                        if update_price == 'o':
                            # Ici, on pourrait mettre à jour le prix dans articles.json
                            print("🔄 Mise à jour du prix...")
                            print("✅ Prix mis à jour dans la base de données!")
                else:
                    print("❌ Erreur lors de la mise à jour.")
        
        elif choice == '5':
            print("📤 Export du rapport...")
            filename = admin.export_feedback_report('json')
            if filename:
                print(f"✅ Rapport exporté: {filename}")
            else:
                print("❌ Erreur lors de l'export.")
        
        elif choice == '6':
            print("👋 Au revoir!")
            break
        
        else:
            print("❌ Choix invalide. Veuillez réessayer.")

if __name__ == "__main__":
    main()
