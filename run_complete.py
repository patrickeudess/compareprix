#!/usr/bin/env python3
"""
Script complet pour ComparePrix
1. Scrape les données Jumia
2. Fusionne avec les données existantes
3. Lance l'application Flask
"""

import subprocess

def run_command(command, description):
    """Exécute une commande avec gestion d'erreur"""
    print(f"\n🔄 {description}")
    print(f"Commande: {command}")
    print("-" * 50)
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print("✅ Succès!")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur: {e}")
        if e.stdout:
            print("Sortie:", e.stdout)
        if e.stderr:
            print("Erreur:", e.stderr)
        return False

def main():
    print("🚀 ComparePrix - Script de démarrage complet")
    print("=" * 60)
    
    # Vérifier que Python est installé
    if not run_command("python --version", "Vérification de Python"):
        print("❌ Python n'est pas installé ou n'est pas dans le PATH")
        return
    
    # Installer les dépendances
    if not run_command("pip install -r requirements.txt", "Installation des dépendances"):
        print("❌ Erreur lors de l'installation des dépendances")
        return
    
    # Scraper les données Jumia
    print("\n🛒 Démarrage du scraping Jumia...")
    if run_command("python scraper_jumia_v2.py", "Scraping des produits Jumia"):
        print("✅ Scraping terminé avec succès!")
    else:
        print("⚠️ Erreur lors du scraping, utilisation des données existantes")
    
    # Fusionner les données
    if run_command("python merge_data.py", "Fusion des données"):
        print("✅ Fusion des données terminée!")
    else:
        print("❌ Erreur lors de la fusion des données")
        return
    
    # Lancer l'application Flask
    print("\n🌐 Démarrage de l'application ComparePrix...")
    print("L'application sera accessible à l'adresse: http://localhost:5000")
    print("Appuyez sur Ctrl+C pour arrêter l'application")
    print("-" * 60)
    
    try:
        subprocess.run("python app.py", shell=True, check=True)
    except KeyboardInterrupt:
        print("\n👋 Application arrêtée par l'utilisateur")
    except Exception as e:
        print(f"❌ Erreur lors du démarrage de l'application: {e}")

if __name__ == "__main__":
    main()
