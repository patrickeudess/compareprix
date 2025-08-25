#!/usr/bin/env python3
"""
Service de démarrage pour le système de collecte de données ComparePrix
Gère le démarrage de tous les composants du système
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
import threading

class CollectionService:
    def __init__(self):
        self.config_file = 'config/collection_config.json'
        self.log_file = 'logs/collection_service.log'
        self.processes = {}
        
        # Créer les dossiers nécessaires
        os.makedirs('logs', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        os.makedirs('config', exist_ok=True)
        
        # Charger la configuration
        self.config = self._load_config()
    
    def _load_config(self):
        """Charge la configuration du système"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return self._create_default_config()
    
    def _create_default_config(self):
        """Crée une configuration par défaut"""
        config = {
            "collection_methods": {
                "manual_collection": {"enabled": True},
                "receipt_collection": {"enabled": True},
                "scraping": {"enabled": True}
            },
            "services": {
                "flask_app": {"enabled": True, "port": 5000},
                "whatsapp_bot": {"enabled": False},
                "scraping_scheduler": {"enabled": True},
                "validation_tool": {"enabled": True}
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return config
    
    def start_flask_app(self):
        """Démarre l'application Flask"""
        try:
            print("🌐 Démarrage de l'application Flask...")
            process = subprocess.Popen([
                sys.executable, 'app.py'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.processes['flask_app'] = process
            print(f"✅ Application Flask démarrée (PID: {process.pid})")
            
            # Attendre que l'app soit prête
            time.sleep(3)
            
        except Exception as e:
            print(f"❌ Erreur lors du démarrage de Flask: {e}")
    
    def start_scraping_scheduler(self):
        """Démarre le planificateur de scraping"""
        try:
            print("🤖 Démarrage du planificateur de scraping...")
            
            # Démarrer le scraping initial
            subprocess.run([sys.executable, 'scraper_jumia_v2.py'], 
                         capture_output=True, text=True)
            
            print("✅ Scraping initial terminé")
            
            # Planifier le scraping quotidien
            def run_daily_scraping():
                while True:
                    time.sleep(24 * 60 * 60)  # 24 heures
                    try:
                        print("🔄 Exécution du scraping quotidien...")
                        subprocess.run([sys.executable, 'scraper_jumia_v2.py'], 
                                     capture_output=True, text=True)
                        print("✅ Scraping quotidien terminé")
                    except Exception as e:
                        print(f"❌ Erreur lors du scraping: {e}")
            
            # Démarrer le thread de scraping
            scraping_thread = threading.Thread(target=run_daily_scraping, daemon=True)
            scraping_thread.start()
            
            self.processes['scraping_scheduler'] = scraping_thread
            print("✅ Planificateur de scraping démarré")
            
        except Exception as e:
            print(f"❌ Erreur lors du démarrage du scraping: {e}")
    
    def start_validation_service(self):
        """Démarre le service de validation"""
        try:
            print("✅ Démarrage du service de validation...")
            
            def run_validation_monitor():
                while True:
                    time.sleep(60 * 60)  # 1 heure
                    try:
                        # Vérifier les validations en attente
                        from validation_tool import ValidationTool
                        tool = ValidationTool()
                        pending = tool.get_pending_validations()
                        
                        if pending:
                            print(f"⚠️ {len(pending)} validations en attente")
                        
                        # Vérifier les anomalies
                        anomalies = tool.check_price_anomalies()
                        if anomalies:
                            print(f"🚨 {len(anomalies)} anomalies détectées")
                            
                    except Exception as e:
                        print(f"❌ Erreur lors de la validation: {e}")
            
            # Démarrer le thread de validation
            validation_thread = threading.Thread(target=run_validation_monitor, daemon=True)
            validation_thread.start()
            
            self.processes['validation_service'] = validation_thread
            print("✅ Service de validation démarré")
            
        except Exception as e:
            print(f"❌ Erreur lors du démarrage de la validation: {e}")
    
    def start_whatsapp_bot(self):
        """Démarre le bot WhatsApp (si configuré)"""
        if not self.config.get('services', {}).get('whatsapp_bot', {}).get('enabled', False):
            print("📱 Bot WhatsApp désactivé dans la configuration")
            return
        
        try:
            print("📱 Démarrage du bot WhatsApp...")
            # Ici, on démarrerait le bot WhatsApp
            # Pour l'instant, simulation
            print("✅ Bot WhatsApp démarré (simulation)")
            
        except Exception as e:
            print(f"❌ Erreur lors du démarrage du bot WhatsApp: {e}")
    
    def run_initial_setup(self):
        """Exécute la configuration initiale"""
        print("🔧 Configuration initiale du système...")
        
        # Vérifier les dépendances
        try:
            import flask
            import requests
            import bs4 # type: ignore
            print("✅ Toutes les dépendances sont installées")
        except ImportError as e:
            print(f"❌ Dépendance manquante: {e}")
            print("💡 Exécutez: pip install -r requirements.txt")
            return False
        
        # Créer les données d'exemple si nécessaire
        if not os.path.exists('data/articles.json'):
            print("📊 Création des données d'exemple...")
            subprocess.run([sys.executable, 'app.py'], 
                         capture_output=True, text=True, timeout=10)
        
        # Tester le système de collecte
        print("🧪 Test du système de collecte...")
        subprocess.run([sys.executable, 'test_collection_system.py'], 
                     capture_output=True, text=True)
        
        print("✅ Configuration initiale terminée")
        return True
    
    def start_all_services(self):
        """Démarre tous les services"""
        print("🚀 Démarrage du système de collecte ComparePrix")
        print("=" * 60)
        
        # Configuration initiale
        if not self.run_initial_setup():
            print("❌ Échec de la configuration initiale")
            return
        
        # Démarrer les services selon la configuration
        services_config = self.config.get('services', {})
        
        if services_config.get('flask_app', {}).get('enabled', True):
            self.start_flask_app()
        
        if services_config.get('scraping_scheduler', {}).get('enabled', True):
            self.start_scraping_scheduler()
        
        if services_config.get('validation_tool', {}).get('enabled', True):
            self.start_validation_service()
        
        if services_config.get('whatsapp_bot', {}).get('enabled', False):
            self.start_whatsapp_bot()
        
        print("\n🎉 Tous les services sont démarrés!")
        print("\n📊 Services actifs:")
        for service_name, process in self.processes.items():
            if hasattr(process, 'pid'):
                print(f"   - {service_name}: PID {process.pid}")
            else:
                print(f"   - {service_name}: Thread actif")
        
        print(f"\n🌐 Application web: http://localhost:5000")
        print(f"📁 Logs: logs/collection_service.log")
        print(f"⚙️ Configuration: config/collection_config.json")
        
        print("\n💡 Commandes utiles:")
        print("   - Validation: python validation_tool.py")
        print("   - Test: python test_collection_system.py")
        print("   - Arrêt: Ctrl+C")
        
        return True
    
    def stop_all_services(self):
        """Arrête tous les services"""
        print("\n🛑 Arrêt des services...")
        
        for service_name, process in self.processes.items():
            try:
                if hasattr(process, 'terminate'):
                    process.terminate()
                    process.wait(timeout=5)
                    print(f"✅ {service_name} arrêté")
                else:
                    print(f"✅ {service_name} arrêté (thread)")
            except Exception as e:
                print(f"❌ Erreur lors de l'arrêt de {service_name}: {e}")
        
        print("👋 Tous les services sont arrêtés")
    
    def get_status(self):
        """Affiche le statut des services"""
        print("📊 Statut des services:")
        print("-" * 30)
        
        for service_name, process in self.processes.items():
            if hasattr(process, 'poll'):
                status = "Actif" if process.poll() is None else "Arrêté"
                print(f"   - {service_name}: {status}")
            else:
                print(f"   - {service_name}: Thread actif")
    
    def monitor_services(self):
        """Surveille les services en cours d'exécution"""
        try:
            while True:
                time.sleep(30)  # Vérifier toutes les 30 secondes
                
                # Vérifier que Flask est toujours actif
                if 'flask_app' in self.processes:
                    process = self.processes['flask_app']
                    if process.poll() is not None:
                        print("⚠️ Application Flask arrêtée, redémarrage...")
                        self.start_flask_app()
                
        except KeyboardInterrupt:
            print("\n🛑 Arrêt demandé par l'utilisateur")
            self.stop_all_services()

def main():
    """Fonction principale"""
    service = CollectionService()
    
    try:
        # Démarrer tous les services
        if service.start_all_services():
            # Surveiller les services
            service.monitor_services()
    except KeyboardInterrupt:
        print("\n🛑 Arrêt demandé par l'utilisateur")
    finally:
        service.stop_all_services()

if __name__ == "__main__":
    main()
