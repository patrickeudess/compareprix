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


# ---------------------------------------------------------------- prix unitaire

import json
import os
import re
import statistics
from collections import defaultdict, namedtuple

Quantity = namedtuple('Quantity', 'value base')  # value exprimée en kg ou en L

# unité lue dans le nom -> (unité de base, facteur vers l'unité de base)
_UNITS = {'kg': ('kg', 1), 'g': ('kg', 0.001), 'l': ('L', 1), 'litre': ('L', 1), 'litres': ('L', 1),
          'cl': ('L', 0.01), 'ml': ('L', 0.001)}
_NUM = r'(\d+(?:[.,]\d+)?)'
_UNIT_RE = r'(kg|g|litres?|l|cl|ml)'
# "6x1L", "6 x 1,5 L"  |  "1L x6", "33cl x 6"  |  "5 kg", "750ml"
_MULT_BEFORE = re.compile(rf'(?<![\d.,])(\d+)\s*[x×*]\s*{_NUM}\s*{_UNIT_RE}\b', re.I)
_MULT_AFTER = re.compile(rf'(?<![\d.,]){_NUM}\s*{_UNIT_RE}\s*[x×*]\s*(\d+)\b', re.I)
_SINGLE = re.compile(rf'(?<![\d.,]){_NUM}\s*{_UNIT_RE}\b', re.I)

# Écart max (%) par rapport à la médiane avant de signaler un prix : config/collection_config.json
DEFAULT_MAX_DEVIATION_PCT = 20
MIN_POINTS_FOR_ANOMALY = 3  # une médiane sur 2 points ne désigne pas un « mauvais » prix


def _num(text):
    return float(text.replace(',', '.'))


def parse_quantity(name):
    """Extrait la quantité du CONDITIONNEMENT depuis le nom : '5 kg', '750ml', '6x1L', '33cl x6'.
    Retourne Quantity(valeur_en_kg_ou_L, 'kg'|'L') ou None. Un multiplicateur est appliqué."""
    text = str(name or '')
    m = _MULT_BEFORE.search(text)
    if m:
        count, qty, unit = int(m.group(1)), _num(m.group(2)), m.group(3).lower()
    else:
        m = _MULT_AFTER.search(text)
        if m:
            qty, unit, count = _num(m.group(1)), m.group(2).lower(), int(m.group(3))
        else:
            m = _SINGLE.search(text)
            if not m:
                return None
            count, qty, unit = 1, _num(m.group(1)), m.group(2).lower()
    base, factor = _UNITS[unit]
    value = count * qty * factor
    return Quantity(value, base) if value > 0 else None


def unit_price(article):
    """Prix ramené au kg, au L ou à l'unité pour comparer des conditionnements différents.

    Règles (dans l'ordre) :
      1. Le nom indique une quantité ('Riz 5kg') -> le prix est celui du conditionnement : prix / quantité.
      2. Sinon, `unite` kg/g/L/cl/ml (ancien format) -> le prix est DÉJÀ rapporté à cette unité,
         sauf pour source 'jumia' : l'unité y est devinée par mots-clés, donc non fiable -> pas de prix unitaire.
      3. Sinon `unite` = 'unité' -> prix par unité ; 'lot' -> non comparable.
    Retourne (prix_unitaire, unite_base, origine) ou (None, None, None). origine : 'nom' | 'declare'."""
    prix = article.get('prix')
    if not isinstance(prix, (int, float)) or prix <= 0:
        return None, None, None
    q = parse_quantity(article.get('article'))
    if q:
        return round(prix / q.value, 2), q.base, 'nom'
    unite = article.get('unite')
    if article.get('source') == 'jumia' and unite not in ('unité', 'lot'):
        return None, None, None
    if unite in ('kg', 'L'):
        return float(prix), unite, 'declare'
    if unite in ('g', 'cl', 'ml'):  # prix par g / cl / ml -> par kg / L
        base, factor = _UNITS[unite]
        return round(prix / factor, 2), base, 'declare'
    if unite == 'unité':
        return float(prix), 'unité', 'declare'
    return None, None, None


def load_max_deviation(path='config/collection_config.json'):
    """Seuil d'écart (%) lu dans la config de qualité, 20 par défaut."""
    try:
        with open(path, encoding='utf-8') as f:
            return float(json.load(f)['quality_control']['price_validation']['max_deviation_percent'])
    except (OSError, ValueError, KeyError, TypeError):
        return DEFAULT_MAX_DEVIATION_PCT


def enrich_results(articles, max_deviation_pct=None):
    """Ajoute à chaque article : prix_unitaire, unite_base, origine_unite, meilleur_prix, anomalie.

    - meilleur_prix : prix unitaire le plus bas parmi les articles de même unité de base.
    - anomalie : {'ecart_pct', 'mediane'} si le prix unitaire s'écarte de plus de `max_deviation_pct`
      de la médiane des magasins pour le MÊME nom d'article (au moins 3 magasins comparables)."""
    threshold = load_max_deviation() if max_deviation_pct is None else max_deviation_pct
    out = []
    for a in articles:
        pu, base, origin = unit_price(a)
        out.append({**a, 'prix_unitaire': pu, 'unite_base': base, 'origine_unite': origin,
                    'meilleur_prix': False, 'anomalie': None})

    best = {}
    groups = defaultdict(list)
    for a in out:
        if a['prix_unitaire'] is None:
            continue
        best[a['unite_base']] = min(best.get(a['unite_base'], float('inf')), a['prix_unitaire'])
        groups[(normalize_key(a['article']), a['unite_base'])].append(a)
    for a in out:
        a['meilleur_prix'] = a['prix_unitaire'] is not None and a['prix_unitaire'] == best[a['unite_base']]

    for members in groups.values():
        if len(members) < MIN_POINTS_FOR_ANOMALY:
            continue
        median = statistics.median(m['prix_unitaire'] for m in members)
        for m in members:
            deviation = (m['prix_unitaire'] - median) / median * 100
            if abs(deviation) > threshold:
                m['anomalie'] = {'ecart_pct': round(deviation, 1), 'mediane': round(median, 2)}
    return out


def normalize_key(name):
    return re.sub(r'\s+', ' ', str(name or '')).strip().lower()
