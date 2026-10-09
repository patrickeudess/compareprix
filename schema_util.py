"""Outils de migration SQLite sûrs quand plusieurs processus démarrent en même temps (Gunicorn, uWSGI...)."""
import sqlite3


def add_column_if_missing(conn, table, column, definition):
    """Ajoute une colonne si elle n'existe pas encore. Retourne True si CE processus l'a ajoutée.

    « Vérifier puis ajouter » seul n'est pas atomique : deux processus qui démarrent ensemble voient tous deux la
    colonne absente, et le second échoue avec « duplicate column name » (le démarrage du worker plante). On tolère
    donc exactement cette erreur : la colonne existe, c'est ce qu'on voulait. Toute autre erreur est relancée."""
    if column in {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}:
        return False
    try:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        return True
    except sqlite3.OperationalError as error:
        if 'duplicate column name' not in str(error).lower():
            raise
        return False
