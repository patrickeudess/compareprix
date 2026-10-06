"""Modèle de données des prix : champs obligatoires, validation et fraîcheur.

Chaque observation de prix porte :
  article, supermarche, prix (FCFA, entier > 0), unite,
  date_releve (AAAA-MM-JJ), source, statut, [url], [image_url]
"""
from datetime import date, datetime

# Seuil de péremption : aligné sur config/collection_config.json (timeliness_threshold)
STALE_DAYS = 7
MAX_PRICE_FCFA = 10_000_000

SOURCES = {'manuel', 'ticket', 'jumia', 'signalement', 'exemple'}
STATUTS = {'valide', 'a_verifier', 'donnee_exemple'}
UNITES = {'kg', 'g', 'L', 'cl', 'ml', 'unité', 'lot'}


def parse_date(value):
    """Retourne un `date` ou None si absent/invalide."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def normalize_article(raw):
    """Complète un enregistrement ancien avec des valeurs par défaut HONNÊTES.

    Un enregistrement sans date ni source est considéré comme donnée d'exemple :
    on ne lui invente jamais une date de relevé.
    """
    a = dict(raw)
    a.setdefault('unite', 'unité')
    a.setdefault('date_releve', None)
    a.setdefault('source', 'jumia' if a.get('supermarche') == 'Jumia' and a.get('date_releve') else 'exemple')
    a.setdefault('statut', 'donnee_exemple' if a['source'] == 'exemple' else 'a_verifier')
    return a


def freshness(article, today=None):
    """'exemple' | 'inconnue' | 'perimee' | 'recente' (+ âge en jours)."""
    today = today or date.today()
    if article.get('statut') == 'donnee_exemple' or article.get('source') == 'exemple':
        return 'exemple', None
    d = parse_date(article.get('date_releve'))
    if d is None:
        return 'inconnue', None
    age = (today - d).days
    return ('perimee' if age > STALE_DAYS else 'recente'), age


def validate_article(a, today=None):
    """Retourne la liste des erreurs (vide = valide). Utilisé par l'import."""
    today = today or date.today()
    errors = []
    for field in ('article', 'supermarche'):
        v = a.get(field)
        if not isinstance(v, str) or not v.strip():
            errors.append(f'{field} manquant')
        elif len(v) > 200:
            errors.append(f'{field} trop long')
    prix = a.get('prix')
    if isinstance(prix, bool) or not isinstance(prix, int) or not (0 < prix <= MAX_PRICE_FCFA):
        errors.append('prix doit être un entier FCFA entre 1 et %d' % MAX_PRICE_FCFA)
    if a.get('unite') not in UNITES:
        errors.append('unite inconnue (%s)' % ', '.join(sorted(UNITES)))
    d = parse_date(a.get('date_releve'))
    if d is None:
        errors.append('date_releve invalide (AAAA-MM-JJ)')
    elif d > today:
        errors.append('date_releve dans le futur')
    if a.get('source') not in SOURCES - {'exemple'}:
        errors.append('source invalide (%s)' % ', '.join(sorted(SOURCES - {'exemple'})))
    if a.get('statut') not in STATUTS - {'donnee_exemple'}:
        errors.append('statut invalide (valide, a_verifier)')
    url = a.get('url')
    if url and not str(url).startswith(('http://', 'https://')):
        errors.append('url doit commencer par http(s)')
    return errors
