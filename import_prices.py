"""Importe des relevés de prix réels depuis un CSV vers la base SQLite (data/compareprix.db).

Usage :
    python import_prices.py data/releve_modele.csv            # simulation (rien n'est écrit)
    python import_prices.py data/releve_modele.csv --apply    # écrit dans la base (sauvegarde auto)
    python import_prices.py releve.csv --apply --replace-examples   # retire aussi les données d'exemple

Colonnes CSV (en-tête obligatoire) :
    article,supermarche,prix,unite,date_releve,source,statut,url,image_url
Une ligne invalide est rejetée avec son numéro ; si une seule ligne est
rejetée, rien n'est écrit (import tout ou rien). Les relevés s'ajoutent à
l'HISTORIQUE ; le prix affiché est le plus récent par (article, supermarche),
donc un relevé plus ancien est conservé mais n'écrase pas le courant.
Un relevé identique déjà présent est ignoré (import rejouable sans doublon).
"""
import argparse
import csv
import os
import sqlite3
import sys
from datetime import datetime

import db
from pricing import validate_article

REQUIRED = ['article', 'supermarche', 'prix', 'unite', 'date_releve', 'source', 'statut']


def read_csv(path):
    rows, errors = [], []
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit('Colonnes manquantes : ' + ', '.join(missing))
        for n, row in enumerate(reader, start=2):  # ligne 1 = en-tête
            rec = {k: (v or '').strip() for k, v in row.items() if k}
            try:
                rec['prix'] = int(rec['prix'])
            except ValueError:
                errors.append((n, ['prix doit être un entier FCFA']))
                continue
            for opt in ('url', 'image_url'):
                if not rec.get(opt):
                    rec.pop(opt, None)
            errs = validate_article(rec)
            if errs:
                errors.append((n, errs))
            else:
                rows.append(rec)
    return rows, errors


def apply_rows(conn, rows, replace_examples=False):
    """Insère les lignes dans la transaction `conn`. Retourne les compteurs."""
    stats = {'ajoutes': 0, 'doublons': 0, 'historique': 0, 'exemples_supprimes': 0}
    if replace_examples:
        stats['exemples_supprimes'] = conn.execute(
            "DELETE FROM price_observation WHERE statut = 'donnee_exemple'").rowcount
    for rec in rows:
        current = db.current_date(conn, rec['article'], rec['supermarche'])
        _, created = db.add_observation(conn, rec)
        if not created:
            stats['doublons'] += 1
        else:
            stats['ajoutes'] += 1
            if current and current > rec['date_releve']:
                stats['historique'] += 1  # conservé, mais le relevé courant reste plus récent
    return stats


def backup_database():
    os.makedirs('data', exist_ok=True)
    path = f"data/backup_compareprix_{datetime.now():%Y%m%d_%H%M%S}.db"
    src, dst = sqlite3.connect(db.db_path()), sqlite3.connect(path)
    with dst:
        src.backup(dst)  # copie cohérente même si l'application écrit
    src.close(); dst.close()
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('csv_file')
    p.add_argument('--apply', action='store_true', help='écrit réellement les données')
    p.add_argument('--replace-examples', action='store_true', help="supprime les données d'exemple")
    args = p.parse_args()

    rows, errors = read_csv(args.csv_file)
    for n, errs in errors:
        print(f'❌ ligne {n} : ' + '; '.join(errs))
    if errors:
        print(f"\nImport annulé : {len(errors)} ligne(s) invalide(s), {len(rows)} valide(s). Rien n'a été écrit.")
        sys.exit(1)

    db.init_db()
    if args.apply:
        print(f'💾 Sauvegarde : {backup_database()}')
    # Même code pour la simulation et l'écriture : la simulation annule la transaction.
    class _Rollback(Exception):
        pass
    try:
        with db.transaction() as conn:
            stats = apply_rows(conn, rows, args.replace_examples)
            if not args.apply:
                raise _Rollback()
    except _Rollback:
        pass
    print(f"✅ {len(rows)} ligne(s) valides → {stats['ajoutes']} ajoutée(s) "
          f"(dont {stats['historique']} plus ancienne(s) que le relevé courant), "
          f"{stats['doublons']} doublon(s) ignoré(s), {stats['exemples_supprimes']} exemple(s) supprimé(s)")
    print(f"📝 Base : {db.db_path()}" if args.apply else 'Simulation uniquement. Relancez avec --apply pour écrire.')


if __name__ == '__main__':
    main()
