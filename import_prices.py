"""Importe des relevés de prix réels depuis un CSV vers data/articles.json.

Usage :
    python import_prices.py data/releve_modele.csv            # simulation (rien n'est écrit)
    python import_prices.py data/releve_modele.csv --apply    # écrit dans data/articles.json
    python import_prices.py releve.csv --apply --replace-examples   # retire aussi les données d'exemple

Colonnes CSV (en-tête obligatoire) :
    article,supermarche,prix,unite,date_releve,source,statut,url,image_url
Une ligne invalide est rejetée avec son numéro ; si une seule ligne est
rejetée, rien n'est écrit (import tout ou rien). Une ligne remplace la
précédente pour la même clé (article, supermarche) uniquement si sa
date_releve est plus récente ou égale.
"""
import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import datetime

from pricing import normalize_article, validate_article

DATA_FILE = 'data/articles.json'
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


def atomic_write(path, data):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.', suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # remplacement atomique


def merge(existing, new_rows, replace_examples=False):
    current = [normalize_article(a) for a in existing]
    if replace_examples:
        current = [a for a in current if a['statut'] != 'donnee_exemple']
    index = {(a['article'].lower(), a['supermarche'].lower()): i for i, a in enumerate(current)}
    added = updated = skipped = 0
    for rec in new_rows:
        key = (rec['article'].lower(), rec['supermarche'].lower())
        if key in index:
            old = current[index[key]]
            if (old.get('date_releve') or '') > rec['date_releve']:
                skipped += 1  # le relevé existant est plus récent
                continue
            current[index[key]] = rec
            updated += 1
        else:
            index[key] = len(current)
            current.append(rec)
            added += 1
    return current, added, updated, skipped


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
        print(f'\nImport annulé : {len(errors)} ligne(s) invalide(s), {len(rows)} valide(s). Rien n\'a été écrit.')
        sys.exit(1)

    existing = json.load(open(DATA_FILE, encoding='utf-8')) if os.path.exists(DATA_FILE) else []
    merged, added, updated, skipped = merge(existing, rows, args.replace_examples)
    print(f'✅ {len(rows)} ligne(s) valides → {added} ajoutée(s), {updated} mise(s) à jour, {skipped} ignorée(s) (plus anciennes)')
    if not args.apply:
        print('Simulation uniquement. Relancez avec --apply pour écrire.')
        return
    if os.path.exists(DATA_FILE):
        backup = f"data/backup_articles_{datetime.now():%Y%m%d_%H%M%S}.json"
        atomic_write(backup, existing)
        print(f'💾 Sauvegarde : {backup}')
    atomic_write(DATA_FILE, merged)
    print(f'📝 {DATA_FILE} : {len(merged)} article(s)')


if __name__ == '__main__':
    main()
