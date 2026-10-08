"""Synchronise les JSON historiques vers la base SQLite (idempotent, sans doublon).

    python migrate_to_sqlite.py

À lancer après tout outil qui écrit encore data/articles.json ou
data/user_feedback.json (anciens outils de collecte, supprimés).
Un relevé déjà présent est ignoré ; l'historique n'est jamais supprimé.
"""
import db

if __name__ == '__main__':
    db.init_db(seed=False)
    stats = db.sync_from_json(force=True)
    print(f"✅ {stats['observations']} relevé(s) ajouté(s), {stats['doublons']} déjà présent(s), "
          f"{stats['feedback']} signalement(s) ajouté(s) → {db.db_path()}")
