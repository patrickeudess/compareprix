"""Vérification d'email et récupération du mot de passe par code à 6 chiffres.

Principes :
- L'email est facultatif : l'inscription par téléphone reste immédiate. Un email vérifié sert à récupérer
  le mot de passe, et peut être exigé pour contribuer (COMPAREPRIX_REQUIRE_VERIFIED_EMAIL=true).
- Le code n'est jamais stocké : seule son empreinte HMAC (clé de session) l'est. Il expire en 15 minutes,
  n'est valable qu'une fois et s'invalide après 5 essais faux.
- La demande de récupération répond toujours la même chose, qu'un compte existe ou non (pas d'énumération).
- Sans SMTP configuré (voir mailer.py), les routes répondent 503 et l'interface masque la fonctionnalité.
"""
import hashlib
import hmac
import re
import secrets
import smtplib
import sqlite3
import time

from flask import jsonify, request, session
from werkzeug.security import generate_password_hash

import mailer
from ratelimit import SlidingWindowLimiter

CODE_TTL_SECONDS = 15 * 60
MAX_ATTEMPTS = 5

def clock():
    """Horloge isolée : les tests la décalent sans toucher au cookie de session."""
    return time.time()


EMAIL_RE = re.compile(r'[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s.]{2,}')


def normalize_phone(raw):
    """Numéro au format +indicatif, ou None. 10 chiffres = Côte d'Ivoire (+225)."""
    if not isinstance(raw, str) or len(raw) > 40:
        return None
    phone = re.sub(r'[\s().-]', '', raw)
    if phone.startswith('00'):
        phone = '+' + phone[2:]
    if re.fullmatch(r'[0-9]{10}', phone):
        phone = '+225' + phone
    return phone if re.fullmatch(r'\+[1-9][0-9]{7,14}', phone) else None


def normalize_email(raw):
    if not isinstance(raw, str):
        return None
    email = raw.strip().lower()
    return email if len(email) <= 254 and EMAIL_RE.fullmatch(email) else None


def mask_email(email):
    if not email:
        return None
    local, _, domain = email.partition('@')
    return f'{local[:1]}***@{domain}'


def register_verification(app, db, user, csrf_ok, error, now):
    """Ajoute les colonnes, la table de codes et les 4 routes. `db`, `user`, `csrf_ok`, `error`, `now`
    sont les aides de collaboration.py."""
    with db() as conn:
        cols = {row['name'] for row in conn.execute('PRAGMA table_info(users)')}
        for name in ('contact_email', 'email_verified_at'):
            if name not in cols:
                conn.execute(f'ALTER TABLE users ADD COLUMN {name} TEXT')
        # Un même email vérifié ne peut appartenir qu'à un seul compte.
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_verified_email_unique '
                     'ON users(contact_email) WHERE email_verified_at IS NOT NULL')
        conn.execute('''CREATE TABLE IF NOT EXISTS verification_codes (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          purpose TEXT NOT NULL, email TEXT NOT NULL, code_hash TEXT NOT NULL,
          expires_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
          used INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)''')

    per_user = SlidingWindowLimiter(3, 15 * 60)      # 3 codes / 15 min / compte
    per_phone = SlidingWindowLimiter(3, 60 * 60)     # 3 récupérations / heure / numéro
    per_ip = SlidingWindowLimiter(10, 60 * 60)       # 10 demandes / heure / adresse

    def digest(purpose, user_id, email, code):
        message = f'{purpose}:{user_id}:{email}:{code}'.encode()
        return hmac.new(app.secret_key.encode(), message, hashlib.sha256).hexdigest()

    def issue_code(user_id, purpose, email):
        """Crée un code (les précédents deviennent invalides), l'envoie, puis le retire si l'envoi échoue."""
        code = f'{secrets.randbelow(10 ** 6):06d}'
        with db() as conn:
            conn.execute('UPDATE verification_codes SET used=1 WHERE user_id=? AND purpose=? AND used=0', (user_id, purpose))
            cursor = conn.execute(
                'INSERT INTO verification_codes(user_id,purpose,email,code_hash,expires_at,created_at) VALUES (?,?,?,?,?,?)',
                (user_id, purpose, email, digest(purpose, user_id, email, code), clock() + CODE_TTL_SECONDS, now()))
            code_id = cursor.lastrowid
        subject = 'ComparePrix : votre code de vérification' if purpose == 'verify_email' else 'ComparePrix : récupération du mot de passe'
        body = (f'Votre code ComparePrix : {code}\n\nIl est valable 15 minutes et ne sert qu\'une fois.\n'
                'Si vous n\'êtes pas à l\'origine de cette demande, ignorez ce message : rien ne sera modifié.\n')
        try:
            mailer.send_mail(email, subject, body)
        except (OSError, smtplib.SMTPException):
            with db() as conn:
                conn.execute('DELETE FROM verification_codes WHERE id=?', (code_id,))
            return False
        return True

    def check_code(user_id, purpose, email, code):
        """True si le code est le bon. Compte les essais ; le code est consommé en cas de succès."""
        if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code.strip()):
            return False
        with db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM verification_codes WHERE user_id=? AND purpose=? AND used=0 '
                               'ORDER BY id DESC LIMIT 1', (user_id, purpose)).fetchone()
            if not row or row['expires_at'] < clock() or row['attempts'] >= MAX_ATTEMPTS or row['email'] != email:
                return False
            ok = hmac.compare_digest(row['code_hash'], digest(purpose, user_id, email, code.strip()))
            if ok:
                conn.execute('UPDATE verification_codes SET used=1 WHERE id=?', (row['id'],))
            else:
                conn.execute('UPDATE verification_codes SET attempts=attempts+1, used=(attempts+1>=?) WHERE id=?',
                             (MAX_ATTEMPTS, row['id']))
            return ok

    def unavailable():
        return error('L\'envoi d\'email n\'est pas activé sur ce serveur.', 503)

    def wait(retry):
        return error(f'Trop de demandes. Réessayez dans {max(1, retry // 60)} minute(s).', 429)

    def json_body():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    @app.post('/api/account/email/request')
    def email_request():
        current = user()
        if not current:
            return error('Connectez-vous d\'abord.', 401)
        if not csrf_ok():
            return error('Session expirée. Actualisez la page.', 403)
        if not mailer.is_configured():
            return unavailable()
        email = normalize_email(json_body().get('email'))
        if not email:
            return error('Indiquez une adresse email valide.')
        allowed, retry = per_user.check(current['id'])
        if not allowed:
            return wait(retry)
        with db() as conn:
            taken = conn.execute('SELECT id FROM users WHERE contact_email=? AND email_verified_at IS NOT NULL AND id<>?',
                                 (email, current['id'])).fetchone()
        if taken:
            return error('Cette adresse est déjà utilisée par un autre compte.', 409)
        if not issue_code(current['id'], 'verify_email', email):
            return error('L\'email n\'a pas pu être envoyé. Réessayez plus tard.', 502)
        return jsonify(message=f'Un code à 6 chiffres vient d\'être envoyé à {mask_email(email)}. Il est valable 15 minutes.')

    @app.post('/api/account/email/confirm')
    def email_confirm():
        current = user()
        if not current:
            return error('Connectez-vous d\'abord.', 401)
        if not csrf_ok():
            return error('Session expirée. Actualisez la page.', 403)
        data = json_body()
        email = normalize_email(data.get('email'))
        if not email or not check_code(current['id'], 'verify_email', email, data.get('code')):
            return error('Code incorrect ou expiré. Demandez un nouveau code.', 400)
        try:
            with db() as conn:
                conn.execute('UPDATE users SET contact_email=?, email_verified_at=? WHERE id=?', (email, now(), current['id']))
        except sqlite3.IntegrityError:
            return error('Cette adresse est déjà utilisée par un autre compte.', 409)
        return jsonify(message='Email vérifié. Vous pourrez récupérer votre mot de passe avec ce code.', email=mask_email(email))

    @app.post('/api/account/reset/request')
    def reset_request():
        if not csrf_ok():
            return error('Session expirée. Actualisez la page.', 403)
        if not mailer.is_configured():
            return unavailable()
        phone = normalize_phone(json_body().get('phone'))
        if not phone:
            return error('Indiquez le numéro de téléphone de votre compte.')
        for limiter, key in ((per_ip, request.remote_addr or ''), (per_phone, phone)):
            allowed, retry = limiter.check(key)
            if not allowed:
                return wait(retry)
        with db() as conn:
            found = conn.execute('SELECT id, contact_email FROM users WHERE phone=? AND email_verified_at IS NOT NULL', (phone,)).fetchone()
        if found:
            issue_code(found['id'], 'reset', found['contact_email'])  # l'échec d'envoi reste silencieux pour ne rien révéler
        return jsonify(message='Si ce numéro correspond à un compte avec un email vérifié, un code vient d\'être envoyé à cette adresse.')

    @app.post('/api/account/reset/confirm')
    def reset_confirm():
        if not csrf_ok():
            return error('Session expirée. Actualisez la page.', 403)
        data = json_body()
        phone, password = normalize_phone(data.get('phone')), data.get('password')
        if not phone or not isinstance(password, str) or not 12 <= len(password) <= 256:
            return error('Indiquez votre numéro et un nouveau mot de passe de 12 caractères minimum.')
        allowed, retry = per_ip.check('confirm:' + (request.remote_addr or ''))
        if not allowed:
            return wait(retry)
        with db() as conn:
            found = conn.execute('SELECT id, contact_email FROM users WHERE phone=? AND email_verified_at IS NOT NULL', (phone,)).fetchone()
        if not found or not check_code(found['id'], 'reset', found['contact_email'], data.get('code')):
            return error('Code incorrect ou expiré. Demandez un nouveau code.', 400)
        with db() as conn:
            # session_version+1 : toutes les sessions déjà ouvertes (autre appareil, cookie volé) cessent d'être valides.
            conn.execute('UPDATE users SET password_hash=?, session_version=session_version+1 WHERE id=?', (generate_password_hash(password), found['id']))
            conn.execute('UPDATE verification_codes SET used=1 WHERE user_id=?', (found['id'],))
        session.clear()
        session['csrf'] = secrets.token_hex(32)
        return jsonify(message='Mot de passe modifié. Connectez-vous avec le nouveau.', csrf=session['csrf'])
