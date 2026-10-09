"""Importe les prix de référence nationaux (plafonds légaux, moyennes de marché) depuis un CSV.

    python import_references.py data/references_modele.csv            # simulation (rien n'est écrit)
    python import_references.py data/references_modele.csv --apply    # écrit dans la base (sauvegarde auto)

Colonnes (en-tête obligatoire) :
    kind,label,include,exclude,unit_base,qty_value,value,zone,source_name,source_url,valid_from,valid_to,verified

  kind         plafond | moyenne_marche
  label        libellé affiché, par exemple « Huile de palme raffinée 90 cl »
  include      mots-clés TOUS requis dans le nom du produit, séparés par des virgules : « huile,palme »
  exclude      mots-clés qui écartent le produit (facultatif) : « olive,coco »
  unit_base    kg | L
  qty_value    plafond : quantité du format visé dans l'unité de base (0,9 pour 90 cl ; 22,5 pour 22,5 kg) ; moyenne : vide
  value        plafond : prix du format en FCFA entier ; moyenne : FCFA par kg ou L
  zone         zone d'application, par exemple « Abidjan » (vide = nationale)
  source_name  organisme qui publie le chiffre, par exemple « CNLVC »
  source_url   adresse de la source officielle (obligatoire si verified = oui)
  valid_from   AAAA-MM-JJ (obligatoire)         valid_to  AAAA-MM-JJ (obligatoire pour une moyenne)
  verified     oui | non. SEULES les lignes « oui » sont visibles des utilisateurs : mettez « oui » après avoir
               recopié le chiffre depuis la source officielle, jamais depuis un article de presse.

Tout ou rien : si une seule ligne est invalide, rien n'est écrit. Le rejeu du même fichier ne crée pas de doublon.
"""
import argparse
import csv
import io
import sys
from datetime import date

import db
from backup_db import create_backup
from import_prices import decode_csv, normalize_date, normalize_price
from pricing import MAX_PRICE_FCFA, parse_date

REQUIRED = ['kind', 'label', 'include', 'unit_base', 'value', 'source_name', 'valid_from']
KINDS = {'plafond', 'moyenne_marche'}


def _number(text):
    try:
        return float(str(text).replace(',', '.').strip())
    except ValueError:
        return None


def validate_reference(rec):
    """Retourne la liste des erreurs d'une ligne déjà nettoyée (vide si valide)."""
    errors = []
    if rec['kind'] not in KINDS:
        errors.append('kind doit être plafond ou moyenne_marche')
    if not rec['label']:
        errors.append('label manquant')
    if not [t for t in rec['include'].split(',') if t.strip()]:
        errors.append('include : au moins un mot-clé')
    if rec['unit_base'] not in ('kg', 'L'):
        errors.append('unit_base doit être kg ou L')
    if not isinstance(rec['value'], int) or not 0 < rec['value'] <= MAX_PRICE_FCFA:
        errors.append('value doit être un entier FCFA positif')
    if rec['kind'] == 'plafond' and not (isinstance(rec.get('qty_value'), float) and rec['qty_value'] > 0):
        errors.append('qty_value obligatoire pour un plafond (quantité du format, en kg ou L)')
    if rec['kind'] == 'moyenne_marche' and rec.get('qty_value') is not None:
        errors.append('qty_value doit rester vide pour une moyenne')
    if not rec['source_name']:
        errors.append('source_name manquant')
    start, end = parse_date(rec['valid_from']), parse_date(rec['valid_to']) if rec['valid_to'] else None
    if start is None:
        errors.append('valid_from invalide (AAAA-MM-JJ)')
    if rec['valid_to'] and end is None:
        errors.append('valid_to invalide (AAAA-MM-JJ)')
    if start and end and end < start:
        errors.append('valid_to antérieure à valid_from')
    if rec['kind'] == 'moyenne_marche' and not rec['valid_to']:
        errors.append('valid_to obligatoire pour une moyenne (une moyenne vieillit vite)')
    if rec['verified'] not in ('oui', 'non'):
        errors.append('verified doit être oui ou non')
    if rec['verified'] == 'oui' and not rec['source_url'].startswith(('http://', 'https://')):
        errors.append('source_url (http ou https) obligatoire pour une référence vérifiée')
    elif rec['source_url'] and not rec['source_url'].startswith(('http://', 'https://')):
        errors.append('source_url doit commencer par http(s)')
    return errors


def parse_csv(f):
    """Lit le CSV. Retourne (lignes_valides, erreurs [(n°, [messages])], ignorees). Une ligne entièrement vide
    ou sans `value` est ignorée (modèle pas encore rempli)."""
    text = f.read()
    header = text.splitlines()[0] if text.strip() else ''
    delimiter = ';' if header.count(';') > header.count(',') else ','
    reader = csv.DictReader(io.StringIO(text, newline=''), delimiter=delimiter)
    missing = [c for c in REQUIRED + ['verified'] if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError('Colonnes manquantes : ' + ', '.join(missing))
    rows, errors, skipped = [], [], 0
    for n, row in enumerate(reader, start=2):
        raw = {k: (v or '').strip() for k, v in row.items() if k}
        if not raw.get('value'):
            skipped += 1
            continue
        qty = raw.get('qty_value', '')
        rec = {
            'kind': raw['kind'].lower(), 'label': raw['label'], 'include': raw['include'],
            'exclude': raw.get('exclude', ''), 'unit_base': 'L' if raw['unit_base'].lower() == 'l' else raw['unit_base'].lower(),
            'qty_value': _number(qty) if qty else None, 'zone': raw.get('zone', ''), 'source_name': raw['source_name'],
            'source_url': raw.get('source_url', ''), 'valid_from': normalize_date(raw['valid_from']),
            'valid_to': normalize_date(raw.get('valid_to', '')), 'verified': raw.get('verified', '').lower(),
        }
        price = normalize_price(raw['value'])
        rec['value'] = int(price) if price.isdigit() else raw['value']
        problems = validate_reference(rec)
        if qty and rec['qty_value'] is None:
            problems.append('qty_value illisible')
        if problems:
            errors.append((n, problems))
        else:
            rec['verified'] = rec['verified'] == 'oui'
            rows.append(rec)
    return rows, errors, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('csv_file')
    parser.add_argument('--apply', action='store_true', help='écrit réellement les données')
    args = parser.parse_args()
    with open(args.csv_file, 'rb') as f:
        try:
            rows, errors, skipped = parse_csv(io.StringIO(decode_csv(f.read())))
        except ValueError as e:
            raise SystemExit(str(e))
    if skipped:
        print(f'ℹ️ {skipped} ligne(s) sans valeur ignorée(s)')
    for n, problems in errors:
        print(f'❌ ligne {n} : ' + '; '.join(problems))
    if errors:
        print(f"\nImport annulé : {len(errors)} ligne(s) invalide(s), {len(rows)} valide(s). Rien n'a été écrit.")
        sys.exit(1)
    db.init_db()
    if args.apply:
        print(f"💾 Sauvegarde : {create_backup('data', 'avant_import_', keep=None)}")

    class _Rollback(Exception):
        pass
    added = duplicates = 0
    try:
        with db.transaction() as conn:
            for rec in rows:
                _, created = db.add_reference(conn, rec)
                added, duplicates = added + created, duplicates + (not created)
            if not args.apply:
                raise _Rollback()
    except _Rollback:
        pass
    visible = sum(1 for r in rows if r['verified'])
    print(f'✅ {len(rows)} ligne(s) valides → {added} ajoutée(s), {duplicates} doublon(s) ignoré(s) '
          f'({visible} vérifiée(s), visibles des utilisateurs ; {len(rows) - visible} non vérifiée(s), masquées)')
    print(f'📝 Base : {db.db_path()}' if args.apply else 'Simulation uniquement. Relancez avec --apply pour écrire.')
    print(f'Date du jour : {date.today().isoformat()}')


if __name__ == '__main__':
    main()
