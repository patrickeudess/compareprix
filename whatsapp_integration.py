#!/usr/bin/env python3
"""
Intégration WhatsApp pour la collecte de tickets de caisse
Utilise l'API WhatsApp Business ou une solution similaire
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List
import requests

class WhatsAppCollector:
    def __init__(self):
        self.config_file = 'config/whatsapp_config.json'
        self.receipts_dir = 'data/receipts'
        self.pending_dir = 'data/pending_receipts'
        
        # Créer les dossiers nécessaires
        os.makedirs(self.receipts_dir, exist_ok=True)
        os.makedirs(self.pending_dir, exist_ok=True)
        os.makedirs('config', exist_ok=True)
        
        # Initialiser la configuration
        self._init_config()
    
    def _init_config(self):
        """Initialise la configuration WhatsApp"""
        if not os.path.exists(self.config_file):
            config = {
                'api_key': '',
                'phone_number': '',
                'webhook_url': '',
                'auto_reply': True,
                'keywords': {
                    'receipt': ['ticket', 'reçu', 'facture', 'caisse'],
                    'supermarket': ['carrefour', 'cap sud', 'casino', 'jumia'],
                    'help': ['aide', 'help', 'comment']
                }
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
    
    def process_whatsapp_message(self, message_data: Dict) -> Dict:
        """
        Traite un message WhatsApp reçu
        
        Args:
            message_data: Données du message WhatsApp
        
        Returns:
            Dict avec statut de traitement
        """
        try:
            # Extraire les informations du message
            sender = message_data.get('sender', '')
            message_text = message_data.get('text', '').lower()
            media_url = message_data.get('media_url', '')
            timestamp = message_data.get('timestamp', datetime.now().isoformat())
            
            # Vérifier si c'est un ticket de caisse
            if self._is_receipt_message(message_text, media_url):
                return self._process_receipt(sender, message_text, media_url, timestamp)
            
            # Vérifier si c'est une demande d'aide
            elif self._is_help_request(message_text):
                return self._send_help_message(sender)
            
            # Message normal
            else:
                return self._process_normal_message(sender, message_text)
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Erreur lors du traitement: {str(e)}'
            }
    
    def _is_receipt_message(self, message_text: str, media_url: str) -> bool:
        """Détermine si le message contient un ticket de caisse"""
        receipt_keywords = ['ticket', 'reçu', 'facture', 'caisse', 'achat']
        
        # Vérifier le texte
        text_contains_keyword = any(keyword in message_text for keyword in receipt_keywords)
        
        # Vérifier s'il y a une image
        has_image = bool(media_url and media_url.endswith(('.jpg', '.jpeg', '.png')))
        
        return text_contains_keyword or has_image
    
    def _is_help_request(self, message_text: str) -> bool:
        """Détermine si c'est une demande d'aide"""
        help_keywords = ['aide', 'help', 'comment', 'comment faire']
        return any(keyword in message_text for keyword in help_keywords)
    
    def _process_receipt(self, sender: str, message_text: str, 
                        media_url: str, timestamp: str) -> Dict:
        """Traite un ticket de caisse"""
        try:
            # Télécharger l'image si présente
            image_path = None
            if media_url:
                image_path = self._download_receipt_image(media_url, sender)
            
            # Extraire les informations du ticket
            receipt_info = self._extract_receipt_info(message_text, image_path)
            
            # Sauvegarder les données
            receipt_data = {
                'id': self._generate_receipt_id(),
                'sender': sender,
                'timestamp': timestamp,
                'image_path': image_path,
                'extracted_info': receipt_info,
                'status': 'pending_validation',
                'source': 'whatsapp'
            }
            
            # Sauvegarder dans le dossier pending
            filename = f"{receipt_data['id']}.json"
            filepath = os.path.join(self.pending_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(receipt_data, f, ensure_ascii=False, indent=2)
            
            # Envoyer une confirmation
            self._send_confirmation_message(sender, receipt_data['id'])
            
            return {
                'status': 'success',
                'receipt_id': receipt_data['id'],
                'message': 'Ticket de caisse reçu et en cours de traitement'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Erreur lors du traitement du ticket: {str(e)}'
            }
    
    def _download_receipt_image(self, media_url: str, sender: str) -> str:
        """Télécharge l'image du ticket"""
        try:
            response = requests.get(media_url, timeout=30)
            response.raise_for_status()
            
            # Créer un nom de fichier unique
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"receipt_{sender}_{timestamp}.jpg"
            filepath = os.path.join(self.receipts_dir, filename)
            
            # Sauvegarder l'image
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filepath
            
        except Exception as e:
            print(f"Erreur lors du téléchargement de l'image: {e}")
            return None
    
    def _extract_receipt_info(self, message_text: str, image_path: str) -> Dict:
        """Extrait les informations du ticket de caisse"""
        # Pour l'instant, extraction basique du texte
        # Dans une vraie implémentation, on utiliserait l'OCR
        
        extracted_info = {
            'supermarket': self._extract_supermarket(message_text),
            'total_amount': self._extract_total_amount(message_text),
            'date': self._extract_date(message_text),
            'products': self._extract_products(message_text),
            'confidence': 0.7  # Score de confiance
        }
        
        return extracted_info
    
    def _extract_supermarket(self, text: str) -> str:
        """Extrait le nom du supermarché"""
        supermarkets = ['carrefour', 'cap sud', 'casino', 'jumia']
        
        for supermarket in supermarkets:
            if supermarket in text.lower():
                return supermarket.title()
        
        return 'Inconnu'
    
    def _extract_total_amount(self, text: str) -> float:
        """Extrait le montant total"""
        # Pattern pour trouver les montants
        patterns = [
            r'total[:\s]*(\d+(?:[.,]\d{2})?)',
            r'montant[:\s]*(\d+(?:[.,]\d{2})?)',
            r'(\d+(?:[.,]\d{2})?)\s*fcfa',
            r'(\d+(?:[.,]\d{2})?)\s*cf'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                amount_str = match.group(1).replace(',', '.')
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        
        return 0.0
    
    def _extract_date(self, text: str) -> str:
        """Extrait la date du ticket"""
        # Patterns pour les dates
        patterns = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
            r'(\d{1,2})\s+(\w+)\s+(\d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return datetime.now().strftime('%Y-%m-%d')
    
    def _extract_products(self, text: str) -> List[Dict]:
        """Extrait les produits du ticket"""
        products = []
        
        # Pattern basique pour les produits
        lines = text.split('\n')
        for line in lines:
            # Chercher des patterns comme "Produit Prix"
            product_match = re.search(r'([a-zA-Z\s]+)\s+(\d+(?:[.,]\d{2})?)', line)
            if product_match:
                product_name = product_match.group(1).strip()
                price_str = product_match.group(2).replace(',', '.')
                
                try:
                    price = float(price_str)
                    products.append({
                        'article': product_name,
                        'prix': price,
                        'unite': 'unité'
                    })
                except ValueError:
                    continue
        
        return products
    
    def _send_confirmation_message(self, sender: str, receipt_id: str):
        """Envoie un message de confirmation"""
        message = f"""
✅ Merci ! Votre ticket de caisse a été reçu.

📋 ID: {receipt_id}
⏰ En cours de traitement...

Nous analyserons votre ticket et l'ajouterons à notre base de données pour améliorer la comparaison des prix.

💡 Conseil: Pour de meilleurs résultats, assurez-vous que l'image du ticket soit claire et complète.
        """
        
        # Ici, on enverrait le message via l'API WhatsApp
        print(f"Message de confirmation envoyé à {sender}: {message}")
    
    def _send_help_message(self, sender: str):
        """Envoie un message d'aide"""
        help_message = """
🛒 ComparePrix - Guide d'utilisation

📸 Pour partager un ticket de caisse:
   - Prenez une photo claire du ticket
   - Envoyez-la avec le texte "ticket" ou "reçu"

🏪 Supermarchés supportés:
   - Carrefour
   - Cap Sud
   - Casino
   - Jumia

❓ Besoin d'aide ? Tapez "aide" ou "help"

📊 Vos contributions nous aident à maintenir des prix à jour !
        """
        
        # Ici, on enverrait le message via l'API WhatsApp
        print(f"Message d'aide envoyé à {sender}: {help_message}")
        
        return {
            'status': 'success',
            'message': 'Message d\'aide envoyé'
        }
    
    def _process_normal_message(self, sender: str, message_text: str):
        """Traite un message normal"""
        return {
            'status': 'ignored',
            'message': 'Message normal, pas d\'action requise'
        }
    
    def _generate_receipt_id(self) -> str:
        """Génère un ID unique pour le ticket"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        import random
        random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        return f"R{timestamp}{random_suffix}"
    
    def get_pending_receipts(self) -> List[Dict]:
        """Récupère tous les tickets en attente de validation"""
        pending_receipts = []
        
        if os.path.exists(self.pending_dir):
            for filename in os.listdir(self.pending_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.pending_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            receipt_data = json.load(f)
                            pending_receipts.append(receipt_data)
                    except Exception as e:
                        print(f"Erreur lors de la lecture de {filename}: {e}")
        
        return pending_receipts
    
    def validate_receipt(self, receipt_id: str, validator_name: str, 
                        validation_result: Dict) -> Dict:
        """Valide un ticket de caisse"""
        try:
            # Trouver le fichier du ticket
            filename = f"{receipt_id}.json"
            filepath = os.path.join(self.pending_dir, filename)
            
            if not os.path.exists(filepath):
                return {
                    'status': 'error',
                    'message': f'Ticket {receipt_id} non trouvé'
                }
            
            # Charger les données du ticket
            with open(filepath, 'r', encoding='utf-8') as f:
                receipt_data = json.load(f)
            
            # Ajouter les informations de validation
            receipt_data['validation'] = {
                'validator': validator_name,
                'timestamp': datetime.now().isoformat(),
                'result': validation_result
            }
            
            receipt_data['status'] = 'validated'
            
            # Déplacer vers le dossier validé
            validated_filepath = os.path.join(self.receipts_dir, filename)
            with open(validated_filepath, 'w', encoding='utf-8') as f:
                json.dump(receipt_data, f, ensure_ascii=False, indent=2)
            
            # Supprimer le fichier en attente
            os.remove(filepath)
            
            return {
                'status': 'success',
                'message': f'Ticket {receipt_id} validé avec succès'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Erreur lors de la validation: {str(e)}'
            }

def main():
    """Fonction principale pour tester l'intégration WhatsApp"""
    collector = WhatsAppCollector()
    
    print("📱 Intégration WhatsApp - Collecte de tickets de caisse")
    print("=" * 60)
    
    # Exemple de message WhatsApp
    test_message = {
        'sender': '+2250123456789',
        'text': 'Voici mon ticket de caisse Carrefour, total 2500 FCFA',
        'media_url': 'https://example.com/receipt.jpg',
        'timestamp': datetime.now().isoformat()
    }
    
    # Traiter le message
    result = collector.process_whatsapp_message(test_message)
    print(f"Résultat du traitement: {result}")
    
    # Afficher les tickets en attente
    pending = collector.get_pending_receipts()
    print(f"\nTickets en attente de validation: {len(pending)}")
    
    for receipt in pending:
        print(f"  - {receipt['id']}: {receipt['sender']} ({receipt['extracted_info']['supermarket']})")

if __name__ == "__main__":
    main()
