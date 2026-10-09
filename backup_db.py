"""Sauvegarde cohérente des données de ComparePrix, avec contrôle d'intégrité et rotation.

    python backup_db.py                       # TOUT : prix + comptes/contributions + photos de preuve
    python backup_db.py --dir /sauvegardes --keep 30
    python backup_db.py --main-only           # seulement la base des prix (ancien comportement)
    python backup_db.py --verify data/backups/community_20261009_023000_000000.db   # contrôle un fichier

Ce qui est sauvegardé (dossier de données = COMPAREPRIX_DATA_DIR, « data » par défaut) :
  - compareprix.db    prix, historique, signalements          -> compareprix_AAAAMMJJ_....db
  - community.sqlite3 comptes, contributions, points          -> community_AAAAMMJJ_....db
  - proofs/           photos de preuve (privées)              -> proofs/ (copie incrémentale, rien n'est supprimé)
NON sauvegardé volontairement : .session-secret (sa perte déconnecte tout le monde, sans autre conséquence ; ne
copiez pas un secret dans des sauvegardes) et online-prices.sqlite3 (cache reconstruit automatiquement).

- Utilise l'API de sauvegarde de SQLite : copie cohérente même pendant que l'application écrit.
- Vérifie chaque copie (PRAGMA integrity_check) ; en cas d'échec, la copie est supprimée et le code
  de sortie est 1 (pour qu'une supervision le détecte). Un échec n'empêche pas les autres sauvegardes.
- Rotation : seules les sauvegardes de CE préfixe sont supprimées, jamais d'autres fichiers.
- Ces sauvegardes contiennent des données personnelles : dossier en 0700, fichiers en 0600.

Planification (cron, tous les jours à 02:30) :
    30 2 * * *  cd /chemin/compareprix && python backup_db.py >> data/backup.log 2>&1
PythonAnywhere : onglet « Tasks » (voir docs/EXPLOITATION.md). Docker : docker compose exec web python backup_db.py
Pensez à copier ces fichiers HORS du serveur (une sauvegarde sur le même disque ne protège pas d'une panne du disque).
"""
import argparse
import glob
import os
import shutil
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


COMMUNITY_FILE = 'community.sqlite3'
KEY_TABLES = ('users', 'contributions', 'point_ledger', 'price_observation', 'product', 'store')


def data_dir():
    return os.path.abspath(os.environ.get('COMPAREPRIX_DATA_DIR', 'data'))


def _private(path, mode):
    try:
        os.chmod(path, mode)
    except OSError:  # système de fichiers sans permissions (Windows, partage réseau) : pas bloquant
        pass


def sync_proofs(source_dir, dest_dir):
    """Copie les photos de preuve absentes de la sauvegarde. Les fichiers portent un nom aléatoire et ne sont jamais
    modifiés : on copie les nouveaux et on ne supprime rien. Retourne (copiées, déjà présentes)."""
    copied = present = 0
    if not os.path.isdir(source_dir):
        return 0, 0
    os.makedirs(dest_dir, exist_ok=True)
    _private(dest_dir, 0o700)
    for name in sorted(os.listdir(source_dir)):
        src, dst = os.path.join(source_dir, name), os.path.join(dest_dir, name)
        if not os.path.isfile(src):
            continue
        if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
            present += 1
            continue
        tmp = dst + '.part'
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)  # jamais de fichier partiel sous le vrai nom
        _private(dst, 0o600)
        copied += 1
    return copied, present


def create_full_backup(dest_dir=DEFAULT_DIR, keep=14, folder=None):
    """Sauvegarde les prix, les comptes/contributions et les photos. Chaque élément est indépendant : un échec est
    consigné et les autres continuent. Retourne un rapport {'files', 'proofs_copied', 'proofs_present', 'skipped', 'errors'}."""
    folder = folder or data_dir()
    report = {'files': [], 'proofs_copied': 0, 'proofs_present': 0, 'skipped': [], 'errors': []}
    os.makedirs(dest_dir, exist_ok=True)
    _private(dest_dir, 0o700)
    jobs = [('prix', DEFAULT_PREFIX, db.db_path()),
            ('comptes et contributions', 'community_', os.path.join(folder, COMMUNITY_FILE))]
    for label, prefix, source in jobs:
        if not os.path.exists(source):
            report['skipped'].append(f'{label} : {source} absent (installation neuve ?)')
            continue
        try:
            path = create_backup(dest_dir, prefix, keep=keep, source=source)
            _private(path, 0o600)
            report['files'].append(path)
        except (OSError, RuntimeError, sqlite3.Error) as error:
            report['errors'].append(f'{label} : {error}')
    try:
        report['proofs_copied'], report['proofs_present'] = sync_proofs(os.path.join(folder, 'proofs'),
                                                                        os.path.join(dest_dir, 'proofs'))
    except OSError as error:
        report['errors'].append(f'photos : {error}')
    return report


def describe_backup(path):
    """Contrôle un fichier de sauvegarde : intégrité et nombre de lignes des tables clés (ce qu'il contient vraiment)."""
    conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in KEY_TABLES if t in tables}
    finally:
        conn.close()
    return {'integrity': integrity, 'counts': counts}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--dir', default=DEFAULT_DIR, help=f'dossier des sauvegardes (défaut {DEFAULT_DIR})')
    p.add_argument('--keep', type=int, default=14, help='nombre de sauvegardes conservées par type (défaut 14)')
    p.add_argument('--main-only', action='store_true', help='sauvegarder seulement la base des prix')
    p.add_argument('--verify', metavar='FICHIER', help='contrôler un fichier de sauvegarde (intégrité et contenu)')
    args = p.parse_args()
    if args.verify:
        try:
            info = describe_backup(args.verify)
        except (OSError, sqlite3.Error) as e:
            print(f'❌ Fichier illisible : {e}', file=sys.stderr)
            sys.exit(1)
        print(f"{'✅' if info['integrity'] == 'ok' else '❌'} Intégrité : {info['integrity']}")
        for table, count in info['counts'].items():
            print(f'   {table} : {count} ligne(s)')
        sys.exit(0 if info['integrity'] == 'ok' else 1)
    if args.main_only:
        try:
            path = create_backup(args.dir, keep=args.keep)
        except (OSError, RuntimeError, sqlite3.Error) as e:
            print(f'❌ Sauvegarde échouée : {e}', file=sys.stderr)
            sys.exit(1)
        print(f'✅ Sauvegarde vérifiée : {path} ({os.path.getsize(path)} octets)')
        return
    report = create_full_backup(args.dir, keep=args.keep)
    for path in report['files']:
        print(f'✅ Sauvegarde vérifiée : {path} ({os.path.getsize(path)} octets)')
    print(f"📷 Photos : {report['proofs_copied']} copiée(s), {report['proofs_present']} déjà sauvegardée(s)")
    for line in report['skipped']:
        print(f'ℹ️ Ignoré : {line}')
    for line in report['errors']:
        print(f'❌ {line}', file=sys.stderr)
    if report['errors'] or not report['files']:
        print('❌ Sauvegarde incomplète : vérifiez le dossier de données et l\'espace disque.', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
