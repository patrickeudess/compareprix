"""Couche d'accès SQLite de ComparePrix (bibliothèque standard, aucune dépendance).

Modèle :
    store(id, name)                      supermarchés
    product(id, name, name_norm)         produits (recherche insensible aux accents/casse)
    price_observation(...)               HISTORIQUE complet des relevés (jamais écrasé)
    current_price (vue)                  dernier relevé par (produit, supermarché)
    feedback(...)                        signalements ; un signalement approuvé crée un relevé

Concurrence : mode WAL + busy_timeout ; chaque opération d'écriture est une
transaction. Plusieurs workers Gunicorn peuvent écrire sans perdre de données.
"""
import json
import os
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime

from pricing import normalize_article

DEFAULT_DB = 'data/compareprix.db'
LEGACY_ARTICLES = 'data/articles.json'
LEGACY_FEEDBACK = 'data/user_feedback.json'

SCHEMA = """
CREATE TABLE IF NOT EXISTS store (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS product (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name_norm TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_product_norm ON product(name_norm);

CREATE TABLE IF NOT EXISTS price_observation (
    id          INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES product(id),
    store_id    INTEGER NOT NULL REFERENCES store(id),
    prix        INTEGER NOT NULL CHECK (prix > 0),
    unite       TEXT NOT NULL,
    date_releve TEXT,                       -- AAAA-MM-JJ ; NULL = donnée d'exemple ou prix en ligne non daté
    source      TEXT NOT NULL CHECK (source IN ('manuel','ticket','jumia','signalement','exemple','prix_internet')),
    statut      TEXT NOT NULL CHECK (statut IN ('valide','a_verifier','donnee_exemple')),
    url         TEXT,
    image_url   TEXT,
    meta        TEXT,                       -- JSON : champs propres aux prix en ligne (date_consultation, lieu...)
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_obs_pair ON price_observation(product_id, store_id, date_releve, id);

-- Prix courant = relevé le plus récent (date, puis ordre d'insertion). Un relevé
-- daté l'emporte toujours sur une donnée d'exemple (date NULL).
CREATE VIEW IF NOT EXISTS current_price AS
SELECT o.* FROM price_observation o
WHERE o.id = (SELECT o2.id FROM price_observation o2
              WHERE o2.product_id = o.product_id AND o2.store_id = o.store_id
              ORDER BY COALESCE(o2.date_releve, '') DESC, o2.id DESC LIMIT 1);

-- Prix de référence nationaux (plafonds légaux, moyennes de marché). Jamais affichés tant que `verified` = 0.
CREATE TABLE IF NOT EXISTS reference_price (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('plafond','moyenne_marche')),
    label       TEXT NOT NULL,
    include     TEXT NOT NULL,              -- mots-clés TOUS requis dans le nom du produit (séparés par des virgules)
    exclude     TEXT NOT NULL DEFAULT '',   -- mots-clés qui écartent le produit
    unit_base   TEXT NOT NULL CHECK (unit_base IN ('kg','L')),
    qty_value   REAL,                       -- plafond : quantité du format visé (en kg ou L) ; moyenne : NULL
    value       INTEGER NOT NULL CHECK (value > 0),  -- plafond : FCFA le format ; moyenne : FCFA par kg ou L
    zone        TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL,
    source_url  TEXT NOT NULL DEFAULT '',
    valid_from  TEXT,
    valid_to    TEXT,
    verified    INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0,1)),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (kind, label, unit_base, qty_value, zone, valid_from)
);

CREATE TABLE IF NOT EXISTS feedback (
    id                     TEXT PRIMARY KEY,
    timestamp              TEXT NOT NULL,
    date                   TEXT NOT NULL,
    product_name           TEXT NOT NULL,
    supermarket            TEXT NOT NULL,
    current_price          INTEGER NOT NULL,
    new_price              INTEGER NOT NULL,
    price_difference       INTEGER NOT NULL,
    feedback_type          TEXT NOT NULL,
    user_comment           TEXT,
    user_name              TEXT,
    user_email             TEXT,
    photo_path             TEXT,
    status                 TEXT NOT NULL DEFAULT 'pending_review'
        CHECK (status IN ('pending_review','approved','rejected','in_progress')),
    reviewed_by            TEXT,
    review_date            TEXT,
    review_notes           TEXT,
    applied_observation_id INTEGER REFERENCES price_observation(id)
);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status);
"""

FEEDBACK_COLUMNS = ['id', 'timestamp', 'date', 'product_name', 'supermarket', 'current_price',
                    'new_price', 'price_difference', 'feedback_type', 'user_comment', 'user_name',
                    'user_email', 'photo_path', 'status', 'reviewed_by', 'review_date', 'review_notes']


def db_path():
    return os.environ.get('COMPAREPRIX_DB', DEFAULT_DB)


def normalize_text(value):
    """minuscules, sans accents, espaces compactés : 'Pâtes  Spaghetti' -> 'pates spaghetti'."""
    s = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s).strip().lower()


def _connect():
    path = db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, isolation_level=None)  # transactions explicites
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA busy_timeout = 15000')
    return conn


@contextmanager
def transaction(write=True):
    """Transaction auto-validée ; `write=True` prend le verrou d'écriture dès le début
    (BEGIN IMMEDIATE) pour éviter les deadlocks lecture→écriture entre workers."""
    conn = _connect()
    try:
        conn.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        yield conn
        conn.execute('COMMIT')
    except BaseException:
        if conn.in_transaction:
            conn.execute('ROLLBACK')
        raise
    finally:
        conn.close()


# Champs propres aux prix en ligne (source 'prix_internet'), stockés en JSON dans price_observation.meta
META_FIELDS = ('date_consultation', 'disponibilite', 'prix_unitaire', 'unite_reference', 'lieu', 'source_catalogue')


def _migrate_observation_table(conn):
    """Migration des bases créées avant 'prix_internet'.

    SQLite ne sait pas modifier une contrainte CHECK : on reconstruit la table (procédure officielle en
    12 étapes), données et identifiants conservés (les signalements y font référence). Idempotent."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='price_observation'").fetchone()
    if row is None or "'prix_internet'" in row['sql']:
        return
    ddl = re.search(r'CREATE TABLE IF NOT EXISTS price_observation \(.*?\n\);', SCHEMA, re.S).group(0)
    ddl = ddl.replace('IF NOT EXISTS price_observation', 'price_observation_new', 1)
    columns = [c['name'] for c in conn.execute('PRAGMA table_info(price_observation)')]
    conn.execute('PRAGMA foreign_keys = OFF')  # sans effet dans une transaction : à positionner avant BEGIN
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('DROP VIEW IF EXISTS current_price')
        conn.execute('DROP TABLE IF EXISTS price_observation_new')
        conn.execute(ddl)
        cols = ','.join(columns)
        conn.execute(f'INSERT INTO price_observation_new({cols}) SELECT {cols} FROM price_observation')
        conn.execute('DROP TABLE price_observation')
        conn.execute('ALTER TABLE price_observation_new RENAME TO price_observation')
        if conn.execute('PRAGMA foreign_key_check').fetchall():
            raise sqlite3.IntegrityError('migration price_observation : références orphelines')
        conn.execute('COMMIT')
    except BaseException:
        if conn.in_transaction:
            conn.execute('ROLLBACK')
        raise
    finally:
        conn.execute('PRAGMA foreign_keys = ON')


def init_db(seed=True):
    """Crée le schéma (idempotent), migre une ancienne base si besoin et, si la base est vide,
    importe les JSON historiques."""
    conn = _connect()
    try:
        conn.execute('PRAGMA journal_mode = WAL')
        conn.executescript(SCHEMA)
        _migrate_observation_table(conn)
        conn.executescript(SCHEMA)  # recrée l'index et la vue supprimés par la migration
    finally:
        conn.close()
    if seed:
        sync_from_json()


# ---------------------------------------------------------------- relevés de prix

def _get_or_create(conn, table, name):
    row = conn.execute(f'SELECT id FROM {table} WHERE name = ?', (name,)).fetchone()
    if row:
        return row['id']
    if table == 'product':
        cur = conn.execute('INSERT INTO product(name, name_norm) VALUES (?, ?)', (name, normalize_text(name)))
    else:
        cur = conn.execute('INSERT INTO store(name) VALUES (?)', (name,))
    return cur.lastrowid


def current_date(conn, article, supermarche):
    """Date du relevé courant pour (article, supermarché) ou None."""
    row = conn.execute(
        'SELECT c.date_releve FROM current_price c JOIN product p ON p.id=c.product_id '
        'JOIN store s ON s.id=c.store_id WHERE p.name=? AND s.name=?', (article, supermarche)).fetchone()
    return row['date_releve'] if row else None


def add_observation(conn, a):
    """Insère un relevé. Retourne (id, créé).

    Identité d'un relevé : produit, magasin, prix, unité, date, source, statut. Un relevé identique est un
    doublon (import rejouable). Corriger l'UNITÉ le même jour crée un nouveau relevé : à date égale c'est le
    plus récent qui s'affiche, l'ancien reste dans l'historique. Pour un doublon, une URL ou une image
    nouvelle (non vide) complète le relevé existant : ce sont des métadonnées, pas une identité."""
    a = normalize_article(a)
    pid = _get_or_create(conn, 'product', a['article'].strip())
    sid = _get_or_create(conn, 'store', a['supermarche'].strip())
    url, image_url = a.get('url') or None, a.get('image_url') or None
    meta = {k: a[k] for k in META_FIELDS if a.get(k) is not None}
    meta = json.dumps(meta, ensure_ascii=False, sort_keys=True) if meta else None
    dup = conn.execute(
        'SELECT id FROM price_observation WHERE product_id=? AND store_id=? AND prix=? AND unite=? '
        'AND date_releve IS ? AND source=? AND statut=?',
        (pid, sid, a['prix'], a['unite'], a['date_releve'], a['source'], a['statut'])).fetchone()
    if dup:
        if url or image_url or meta:
            conn.execute('UPDATE price_observation SET url = COALESCE(?, url), image_url = COALESCE(?, image_url), '
                         'meta = COALESCE(?, meta) WHERE id = ?', (url, image_url, meta, dup['id']))
        return dup['id'], False
    cur = conn.execute(
        'INSERT INTO price_observation(product_id, store_id, prix, unite, date_releve, source, statut, url, image_url, meta) '
        'VALUES (?,?,?,?,?,?,?,?,?,?)',
        (pid, sid, int(a['prix']), a['unite'], a['date_releve'], a['source'], a['statut'], url, image_url, meta))
    return cur.lastrowid, True


def add_reference(conn, rec):
    """Insère une référence. Retourne (id, créée). Une référence identique (même clé unique) est ignorée."""
    key = (rec['kind'], rec['label'], rec['unit_base'], rec.get('qty_value'), rec.get('zone', ''), rec.get('valid_from'))
    dup = conn.execute('SELECT id FROM reference_price WHERE kind=? AND label=? AND unit_base=? AND qty_value IS ? '
                       'AND zone=? AND valid_from IS ?', key).fetchone()
    if dup:
        return dup['id'], False
    cur = conn.execute(
        'INSERT INTO reference_price(kind,label,include,exclude,unit_base,qty_value,value,zone,source_name,source_url,'
        'valid_from,valid_to,verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (rec['kind'], rec['label'], rec['include'], rec.get('exclude', ''), rec['unit_base'], rec.get('qty_value'),
         int(rec['value']), rec.get('zone', ''), rec['source_name'], rec.get('source_url', ''), rec.get('valid_from'),
         rec.get('valid_to'), 1 if rec.get('verified') else 0))
    return cur.lastrowid, True


def list_references(today=None):
    """Références affichables : vérifiées par l'administrateur ET en cours de validité à la date `today`."""
    today = (today or datetime.now().date()).isoformat() if not isinstance(today, str) else today
    conn = _connect()
    try:
        rows = conn.execute(
            'SELECT * FROM reference_price WHERE verified = 1 AND (valid_from IS NULL OR valid_from <= ?) '
            'AND (valid_to IS NULL OR valid_to >= ?) ORDER BY valid_from DESC, id DESC', (today, today)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def import_articles(conn, articles):
    """Importe une liste d'articles (format JSON historique). Retourne (créés, doublons)."""
    created = dup = 0
    for a in articles:
        _, new = add_observation(conn, a)
        created, dup = created + new, dup + (not new)
    return created, dup


_SELECT_CURRENT = (
    'SELECT p.name AS article, s.name AS supermarche, c.prix, c.unite, c.date_releve, c.source, '
    'c.statut, c.url, c.image_url, c.meta FROM current_price c '
    'JOIN product p ON p.id=c.product_id JOIN store s ON s.id=c.store_id ')


def _clean(row):
    d = dict(row)
    meta = d.pop('meta', None)
    if meta:
        d.update(json.loads(meta))
    return {k: v for k, v in d.items() if v is not None or k == 'date_releve'}


def list_current(search=None):
    """Prix courants au format historique de l'API ; `search` = sous-chaîne (sans accents/casse)."""
    sql, params = _SELECT_CURRENT, ()
    if search is not None:
        like = '%' + normalize_text(search).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        sql, params = sql + "WHERE p.name_norm LIKE ? ESCAPE '\\' ", (like,)
    sql += 'ORDER BY p.name_norm, c.prix, s.name'
    with transaction(write=False) as conn:
        return [_clean(r) for r in conn.execute(sql, params)]


def price_history(article, supermarche=None):
    sql = ('SELECT p.name AS article, s.name AS supermarche, o.prix, o.unite, o.date_releve, o.source, o.statut '
           'FROM price_observation o JOIN product p ON p.id=o.product_id JOIN store s ON s.id=o.store_id '
           'WHERE p.name = ? ')
    params = [article]
    if supermarche:
        sql, params = sql + 'AND s.name = ? ', params + [supermarche]
    sql += "ORDER BY s.name, COALESCE(o.date_releve, '') DESC, o.id DESC"
    with transaction(write=False) as conn:
        return [_clean(r) for r in conn.execute(sql, params)]


def recent_observations(limit=50):
    """Derniers relevés saisis (administration) ; `courant` = c'est le prix actuellement affiché."""
    with transaction(write=False) as conn:
        rows = conn.execute(
            'SELECT o.id, p.name AS article, s.name AS supermarche, o.prix, o.unite, o.date_releve, '
            'o.source, o.statut, o.created_at, '
            '(o.id = (SELECT c.id FROM current_price c WHERE c.product_id=o.product_id AND c.store_id=o.store_id)) AS courant '
            'FROM price_observation o JOIN product p ON p.id=o.product_id JOIN store s ON s.id=o.store_id '
            'ORDER BY o.id DESC LIMIT ?', (max(1, min(int(limit), 500)),))
        return [dict(r) for r in rows]


def set_observation_status(observation_id, statut):
    """Passe un relevé de 'a_verifier' à 'valide' (ou inversement). Les données d'exemple sont exclues.
    Retourne True si un relevé a été modifié."""
    if statut not in ('valide', 'a_verifier'):
        raise ValueError('statut invalide')
    with transaction() as conn:
        return conn.execute("UPDATE price_observation SET statut=? WHERE id=? AND statut != 'donnee_exemple'",
                            (statut, observation_id)).rowcount == 1


def delete_observation(observation_id):
    """Supprime un relevé (correction d'une faute de frappe). Retourne 'deleted', 'not_found' ou
    'referenced' (un signalement approuvé s'appuie dessus : on ne casse pas cette trace)."""
    try:
        with transaction() as conn:
            deleted = conn.execute('DELETE FROM price_observation WHERE id = ?', (observation_id,)).rowcount
    except sqlite3.IntegrityError:
        return 'referenced'
    return 'deleted' if deleted else 'not_found'


def get_feedback(feedback_id):
    with transaction(write=False) as conn:
        row = conn.execute('SELECT * FROM feedback WHERE id = ?', (feedback_id,)).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------- signalements

def add_feedback(entry):
    cols = FEEDBACK_COLUMNS
    with transaction() as conn:
        conn.execute(f'INSERT INTO feedback({",".join(cols)}) VALUES ({",".join("?" * len(cols))})',
                     [entry.get(c) for c in cols])


def list_feedback():
    with transaction(write=False) as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM feedback ORDER BY timestamp')]


def set_feedback_status(feedback_id, status, notes='', reviewer='Équipe'):
    """Met à jour un signalement. Approuvé => crée un relevé (une seule fois).

    Retourne None si introuvable, sinon {'applied': bool, 'observation_id': int|None, 'reason': str|None}.
    """
    with transaction() as conn:
        fb = conn.execute('SELECT * FROM feedback WHERE id = ?', (feedback_id,)).fetchone()
        if fb is None:
            return None
        conn.execute('UPDATE feedback SET status=?, review_notes=?, reviewed_by=?, review_date=? WHERE id=?',
                     (status, notes, reviewer, datetime.now().isoformat(), feedback_id))
        result = {'applied': False, 'observation_id': fb['applied_observation_id'], 'reason': None}
        if status != 'approved':
            return result
        if fb['applied_observation_id']:
            result.update(applied=True, reason='déjà appliqué')
            return result
        ref = conn.execute(
            'SELECT c.unite, c.url, c.image_url FROM current_price c JOIN product p ON p.id=c.product_id '
            'JOIN store s ON s.id=c.store_id WHERE p.name=? AND s.name=?',
            (fb['product_name'], fb['supermarket'])).fetchone()
        if ref is None:
            result['reason'] = "produit/supermarché inconnus : aucun relevé de référence (unité inconnue)"
        elif fb['new_price'] <= 0:
            result['reason'] = 'nouveau prix invalide'
        else:
            oid, _ = add_observation(conn, {
                'article': fb['product_name'], 'supermarche': fb['supermarket'], 'prix': fb['new_price'],
                'unite': ref['unite'], 'date_releve': datetime.now().strftime('%Y-%m-%d'),
                'source': 'signalement', 'statut': 'valide', 'url': ref['url'], 'image_url': ref['image_url']})
            conn.execute('UPDATE feedback SET applied_observation_id=? WHERE id=?', (oid, feedback_id))
            result.update(applied=True, observation_id=oid)
        return result


# ---------------------------------------------------------------- migration JSON -> SQLite

def sync_from_json(articles_path=LEGACY_ARTICLES, feedback_path=LEGACY_FEEDBACK, force=False):
    """Importe les JSON historiques. Sans `force`, uniquement si la table est vide (amorçage).
    Idempotent : relancer ne crée aucun doublon. Retourne un dict de compteurs."""
    stats = {'observations': 0, 'doublons': 0, 'feedback': 0}
    with transaction() as conn:
        empty_obs = conn.execute('SELECT COUNT(*) FROM price_observation').fetchone()[0] == 0
        empty_fb = conn.execute('SELECT COUNT(*) FROM feedback').fetchone()[0] == 0
        if os.path.exists(articles_path) and (force or empty_obs):
            with open(articles_path, encoding='utf-8') as f:
                stats['observations'], stats['doublons'] = import_articles(conn, json.load(f))
        if os.path.exists(feedback_path) and (force or empty_fb):
            with open(feedback_path, encoding='utf-8') as f:
                for e in json.load(f):
                    cur = conn.execute(
                        f'INSERT OR IGNORE INTO feedback({",".join(FEEDBACK_COLUMNS)}) '
                        f'VALUES ({",".join("?" * len(FEEDBACK_COLUMNS))})', [e.get(c) for c in FEEDBACK_COLUMNS])
                    stats['feedback'] += cur.rowcount
    return stats
