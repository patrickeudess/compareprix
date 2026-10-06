"""Sauvegarde cohérente de la base SQLite, avec contrôle d'intégrité et rotation.

    python backup_db.py                       # data/backups/, garde les 14 plus récentes
    python backup_db.py --dir /sauvegardes --keep 30

- Utilise l'API de sauvegarde de SQLite : copie cohérente même pendant que l'application écrit.
- Vérifie la copie (PRAGMA integrity_check) ; en cas d'échec, la copie est supprimée et le code
  de sortie est 1 (pour qu'un cron / une supervision le détecte).
- Rotation : seules les sauvegardes de CE préfixe sont supprimées, jamais d'autres fichiers.

Planification (cron, tous les jours à 02:30) :
    30 2 * * *  cd /chemin/compareprix && python backup_db.py >> data/backup.log 2>&1
Docker :  docker compose exec web python backup_db.py
Pensez à copier ces fichiers HORS du serveur (une sauvegarde sur le même disque ne protège pas d'une panne du disque).
"""
import argparse
import glob
import os
import sqlite3
import sys
from datetime import datetime

import db

DEFAULT_DIR = 'data/backups'
DEFAULT_PREFIX = 'compareprix_'


def create_backup(dest_dir=DEFAULT_DIR, prefix=DEFAULT_PREFIX, keep=14, source=None):
    """Crée et vérifie une sauvegarde. Retourne son chemin ; lève RuntimeError si la copie est corrompue."""
    source = source or db.db_path()
    if not os.path.exists(source):
        raise FileNotFoundError(f'Base introuvable : {source}')
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, f'{prefix}{datetime.now():%Y%m%d_%H%M%S_%f}.db')

    src = sqlite3.connect(source)
    dst = sqlite3.connect(path)
    try:
        try:
            with dst:
                src.backup(dst)
            result = dst.execute('PRAGMA integrity_check').fetchone()[0]
        finally:
            src.close()
            dst.close()
        if result != 'ok':
            raise RuntimeError(f'Sauvegarde corrompue ({result})')
    except BaseException:
        if os.path.exists(path):  # jamais de fichier partiel pouvant passer pour une sauvegarde
            os.remove(path)
        raise

    if keep:
        old = sorted(glob.glob(os.path.join(dest_dir, f'{prefix}*.db')))[:-keep]
        for f in old:
            os.remove(f)
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--dir', default=DEFAULT_DIR, help=f'dossier des sauvegardes (défaut {DEFAULT_DIR})')
    p.add_argument('--keep', type=int, default=14, help='nombre de sauvegardes conservées (défaut 14)')
    args = p.parse_args()
    try:
        path = create_backup(args.dir, keep=args.keep)
    except (OSError, RuntimeError, sqlite3.Error) as e:
        print(f'❌ Sauvegarde échouée : {e}', file=sys.stderr)
        sys.exit(1)
    print(f'✅ Sauvegarde vérifiée : {path} ({os.path.getsize(path)} octets)')


if __name__ == '__main__':
    main()
