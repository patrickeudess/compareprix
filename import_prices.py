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
import io
import sys

import db
from backup_db import create_backup
from pricing import validate_article

REQUIRED = ['article', 'supermarche', 'prix', 'unite', 'date_releve', 'source', 'statut']


def decode_csv(raw):
    """Octets -> texte. UTF-8 (avec ou sans BOM) d'abord ; sinon Windows-1252, ce qu'Excel en français
    produit avec « CSV (séparateur : point-virgule) »."""
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('cp1252', errors='replace')


def parse_csv(f):
    """Lit un CSV (objet fichier texte). Retourne (lignes_valides, erreurs, ignorees).

    - Séparateur « , » ou « ; » détecté sur l'en-tête (Excel français utilise « ; »).
    - Une ligne dont `prix` est vide est IGNOREE (fiche de collecte pas encore remplie), pas rejetée :
      on peut donc importer une fiche partiellement remplie. Toute autre anomalie est une erreur."""
    text = f.read()
    header = text.splitlines()[0] if text.strip() else ''
    delimiter = ';' if header.count(';') > header.count(',') else ','
    rows, errors, skipped = [], [], 0
    reader = csv.DictReader(io.StringIO(text, newline=''), delimiter=delimiter)
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError('Colonnes manquantes : ' + ', '.join(missing))
    for n, row in enumerate(reader, start=2):  # ligne 1 = en-tête
        rec = {k: (v or '').strip() for k, v in row.items() if k}
        if not rec.get('prix'):
            skipped += 1
            continue
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
    return rows, errors, skipped


def read_csv(path):
    with open(path, 'rb') as f:
        try:
            return parse_csv(io.StringIO(decode_csv(f.read())))
        except ValueError as e:
            raise SystemExit(str(e))


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


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('csv_file')
    p.add_argument('--apply', action='store_true', help='écrit réellement les données')
    p.add_argument('--replace-examples', action='store_true', help="supprime les données d'exemple")
    args = p.parse_args()

    rows, errors, skipped = read_csv(args.csv_file)
    if skipped:
        print(f'ℹ️ {skipped} ligne(s) sans prix ignorée(s) (fiche non remplie)')
    for n, errs in errors:
        print(f'❌ ligne {n} : ' + '; '.join(errs))
    if errors:
        print(f"\nImport annulé : {len(errors)} ligne(s) invalide(s), {len(rows)} valide(s). Rien n'a été écrit.")
        sys.exit(1)

    db.init_db()
    if args.apply:
        print(f"💾 Sauvegarde : {create_backup('data', 'avant_import_', keep=None)}")
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
