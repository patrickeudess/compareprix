"""Comptes contributeurs, relevés datés et validation privée."""
import os
import json
import secrets
import sqlite3
import hashlib
import re
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from flask import request, session, jsonify, render_template, send_file
from werkzeug.security import generate_password_hash, check_password_hash


def register_collaboration(app, is_admin):
    root = Path(os.environ.get('COMPAREPRIX_DATA_DIR', 'data')).resolve()
    root.mkdir(parents=True, exist_ok=True)
    secret_file = root / '.session-secret'
    if not os.environ.get('COMPAREPRIX_SECRET_KEY') and not secret_file.exists():
        try:
            with secret_file.open('x') as f:
                f.write(secrets.token_hex(32))
        except FileExistsError:
            pass
    app.secret_key = os.environ.get('COMPAREPRIX_SECRET_KEY') or secret_file.read_text().strip()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('COMPAREPRIX_COOKIE_SECURE') == 'true',
                      PERMANENT_SESSION_LIFETIME=timedelta(days=7))
    db_path = root / 'community.sqlite3'

    def db():
        conn = sqlite3.connect(db_path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    with db() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
          password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS contributions (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          article TEXT NOT NULL, brand TEXT NOT NULL, variant TEXT NOT NULL,
          quantity REAL NOT NULL, unit TEXT NOT NULL, price INTEGER NOT NULL,
          store TEXT NOT NULL, location TEXT NOT NULL, observed_at TEXT NOT NULL,
          created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          proof TEXT, proof_hash TEXT UNIQUE, fingerprint TEXT UNIQUE NOT NULL,
          review_note TEXT NOT NULL DEFAULT '', reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS point_ledger (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          contribution_id INTEGER NOT NULL REFERENCES contributions(id),
          kind TEXT NOT NULL, amount INTEGER NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(contribution_id, kind));
        CREATE TABLE IF NOT EXISTS decisions (
          id INTEGER PRIMARY KEY, contribution_id INTEGER NOT NULL REFERENCES contributions(id),
          decision TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts (
          identity TEXT PRIMARY KEY, count INTEGER NOT NULL, until_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS reports (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
          article TEXT NOT NULL, store TEXT NOT NULL, reason TEXT NOT NULL,
          comment TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending');
        ''')
        # Migration additive : conserver les comptes existants et leur historique.
        if 'phone' not in {row['name'] for row in conn.execute('PRAGMA table_info(users)')}:
            conn.execute('ALTER TABLE users ADD COLUMN phone TEXT')
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_phone_unique ON users(phone)')
        columns = {row['name'] for row in conn.execute('PRAGMA table_info(contributions)')}
        for field in ('city', 'district', 'shop'):
            if field not in columns:
                conn.execute(f"ALTER TABLE contributions ADD COLUMN {field} TEXT NOT NULL DEFAULT ''")

    def now():
        return datetime.now(timezone.utc).isoformat()

    @app.after_request
    def private_response_headers(response):
        if request.path.startswith(('/api/account/', '/api/session', '/api/contributions', '/api/reports', '/api/admin/')):
            response.headers['Cache-Control'] = 'private, no-store'
        return response

    def error(message, code=400):
        return jsonify(message=message), code

    def user():
        with db() as conn:
            return conn.execute('SELECT id, phone, name FROM users WHERE id=?', (session.get('uid'),)).fetchone()

    def csrf_ok():
        expected = session.get('csrf', '')
        provided = request.headers.get('X-CSRF-Token', '')
        return bool(expected and provided and secrets.compare_digest(expected.encode(), provided.encode()))

    @app.errorhandler(413)
    def too_large(_error):
        return error('La requête est trop volumineuse. La photo ne doit pas dépasser 5 Mo.', 413)

    def public_prices():
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        with db() as conn:
            rows = conn.execute("SELECT * FROM contributions WHERE status='approved' AND observed_at>=? ORDER BY observed_at DESC,id DESC", (cutoff,)).fetchall()
        latest = {}
        for row in rows:
            key = tuple(str(row[k]).strip().casefold() for k in ('article','brand','variant','quantity','unit','store','location'))
            if key in latest:
                continue
            factor = {'g': .001, 'ml': .001}.get(row['unit'], 1)
            base = {'g': 'kg', 'ml': 'L'}.get(row['unit'], row['unit'])
            latest[key] = dict(article=' · '.join(filter(None, [row['article'],row['brand'],row['variant']])),
                supermarche=row['store'], prix=row['price'], unite=f"{row['quantity']:g} {row['unit']}",
                lieu=row['location'], ville=row['city'], quartier=row['district'], boutique=row['shop'], date_releve=row['observed_at'], source='Contribution validée',
                prix_unitaire=round(row['price'] / (row['quantity'] * factor), 2), unite_reference=base)
        return list(latest.values())

    @app.get('/compte')
    @app.get('/compte.html')
    @app.get('/contribuer')
    @app.get('/contribuer.html')
    def account_page():
        return render_template('community.html', page='contribution' if 'contribuer' in request.path else 'account')

    @app.get('/panier')
    @app.get('/panier.html')
    def basket_page():
        return render_template('basket.html')

    @app.get('/admin/contributions')
    def moderation_page():
        return render_template('moderation.html')

    @app.get('/api/session')
    def get_session():
        session.setdefault('csrf', secrets.token_hex(32))
        current = user()
        return jsonify(user=dict(current) if current else None, csrf=session['csrf'])

    @app.get('/api/locations')
    def locations():
        with db() as conn:
            rows = conn.execute("SELECT DISTINCT city,district,shop,store FROM contributions WHERE status='approved' AND city<>'' AND district<>'' AND shop<>'' ORDER BY city,district,shop").fetchall()
        catalog = json.loads((Path(__file__).resolve().parent / 'static' / 'locations.json').read_text(encoding='utf-8'))
        catalog['locations'] = [dict(row) for row in rows]
        return jsonify(catalog)

    @app.post('/api/account/<action>')
    def account_action(action):
        if not csrf_ok():
            return error('Session expirée. Actualisez la page.', 403)
        if action == 'logout':
            session.clear()
            session['csrf'] = secrets.token_hex(32)
            return jsonify(user=None, csrf=session['csrf'])
        if action not in ('register', 'login'):
            return error('Action inconnue', 404)
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return error('Formulaire invalide')
        phone, password, name = data.get('phone', ''), data.get('password', ''), data.get('name', '')
        if not all(isinstance(v, str) for v in (phone,password,name)):
            return error('Formulaire invalide')
        if len(phone)>40:
            return error('Numéro de téléphone invalide.')
        phone = re.sub(r'[\s().-]', '', phone)
        if phone.startswith('00'):
            phone = '+' + phone[2:]
        if re.fullmatch(r'[0-9]{10}', phone):
            phone = '+225' + phone
        if not re.fullmatch(r'\+[1-9][0-9]{7,14}', phone) or len(password)>256:
            return error('Indiquez 10 chiffres pour un numéro ivoirien, ou un numéro international avec + et son indicatif.')
        identity = hashlib.sha256((request.remote_addr or '').encode()).hexdigest()
        timestamp = datetime.now(timezone.utc).timestamp()
        with db() as conn:
            attempt = conn.execute('SELECT * FROM login_attempts WHERE identity=?', (identity,)).fetchone()
            if attempt and attempt['until_at'] > timestamp and attempt['count'] >= 12:
                return error('Trop de tentatives. Réessayez dans 15 minutes.', 429)
            count = attempt['count'] + 1 if attempt and attempt['until_at'] > timestamp else 1
            conn.execute('INSERT OR REPLACE INTO login_attempts VALUES (?,?,?)', (identity,count,timestamp+900))
        if action == 'register':
            if len(password) < 12 or not name.strip() or len(name.strip()) > 80:
                return error('Indiquez un pseudo et un mot de passe de 12 caractères minimum.')
            try:
                with db() as conn:
                    cursor = conn.execute('INSERT INTO users(email,phone,name,password_hash,created_at) VALUES (?,?,?,?,?)',
                        ('phone:'+phone,phone,name.strip(),generate_password_hash(password),now()))
                    uid = cursor.lastrowid
            except sqlite3.IntegrityError:
                return error('Ce numéro est déjà utilisé. Essayez de vous connecter.', 409)
        else:
            with db() as conn:
                found = conn.execute('SELECT * FROM users WHERE phone=?', (phone,)).fetchone()
            if not found or not check_password_hash(found['password_hash'], password):
                return error('Numéro ou mot de passe incorrect.', 401)
            uid = found['id']
        session.clear()
        session.permanent = True
        session.update(uid=uid, csrf=secrets.token_hex(32))
        with db() as conn:
            conn.execute('DELETE FROM login_attempts WHERE identity=?', (identity,))
        return jsonify(user=dict(user()), csrf=session['csrf'])

    @app.route('/api/contributions', methods=['GET','POST'])
    def contributions():
        current = user()
        if not current:
            return error('Connectez-vous pour envoyer ou consulter vos contributions.', 401)
        if request.method == 'GET':
            with db() as conn:
                rows = conn.execute('SELECT * FROM contributions WHERE user_id=? ORDER BY id DESC', (current['id'],)).fetchall()
                points = conn.execute('SELECT COALESCE(SUM(amount),0) FROM point_ledger WHERE user_id=?', (current['id'],)).fetchone()[0]
            return jsonify(contributions=[{k:r[k] for k in r.keys() if k not in ('user_id','proof_hash','fingerprint')} for r in rows], points=points)
        if not csrf_ok():
            return error('Session expirée. Actualisez la page.', 403)
        data = request.form
        values = {}
        for field, limit, required in [('article',200,True),('brand',100,False),('variant',100,False),('store',120,True),('city',50,True),('district',60,True),('shop',80,True)]:
            value = data.get(field, '').strip()
            if len(value)>limit or (required and not value):
                return error('Vérifiez le produit, le magasin et sa localisation.')
            values[field] = value
        values['location'] = ' · '.join(values[field] for field in ('city','district','shop'))
        try:
            price = int(data.get('price',''))
            quantity = float(data.get('quantity',''))
            observed = date.fromisoformat(data.get('observed_at',''))
        except (ValueError, TypeError):
            return error('Prix, quantité ou date invalide.')
        unit = data.get('unit', '')
        if not 1<=price<=100000000 or not 0.001<=quantity<=100000 or unit not in ('g','kg','ml','L','pièce'):
            return error('Le prix et la quantité doivent être positifs ; choisissez une unité.')
        if observed>date.today() or observed<date.today()-timedelta(days=30):
            return error('Le relevé doit dater des 30 derniers jours et ne peut pas être dans le futur.')
        fingerprint = hashlib.sha256(repr(tuple(values.values())+(quantity,unit,price,observed.isoformat())).casefold().encode()).hexdigest()
        proof_path = proof_hash = None
        upload = request.files.get('photo')
        if upload and upload.filename:
            from PIL import Image, UnidentifiedImageError
            payload = upload.read(5*1024*1024+1)
            if len(payload)>5*1024*1024:
                return error('La photo ne doit pas dépasser 5 Mo.')
            try:
                with Image.open(BytesIO(payload)) as image:
                    if image.format not in ('JPEG','PNG') or image.width*image.height>25000000:
                        return error('Choisissez une photo JPG ou PNG de moins de 25 mégapixels.')
                    image.verify()
                # Réencoder pour retirer métadonnées EXIF et géolocalisation.
                with Image.open(BytesIO(payload)) as image:
                    image = image.convert('RGB')
                    output = BytesIO()
                    image.save(output, format='JPEG', quality=90)
                    clean = output.getvalue()
            except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
                return error('La photo est invalide.')
            proof_hash = hashlib.sha256(clean).hexdigest()
            folder = root / 'proofs'
            folder.mkdir(exist_ok=True)
            proof_path = secrets.token_hex(20)+'.jpg'
            (folder / proof_path).write_bytes(clean)
        try:
            with db() as conn:
                cursor = conn.execute('''INSERT INTO contributions(user_id,article,brand,variant,quantity,unit,price,store,location,observed_at,created_at,proof,proof_hash,fingerprint,city,district,shop)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (current['id'],values['article'],values['brand'],values['variant'],quantity,unit,price,values['store'],values['location'],observed.isoformat(),now(),proof_path,proof_hash,fingerprint,values['city'],values['district'],values['shop']))
                cid = cursor.lastrowid
        except sqlite3.IntegrityError:
            if proof_path:
                (root / 'proofs' / proof_path).unlink(missing_ok=True)
            return error('Ce relevé ou cette photo a déjà été envoyé.', 409)
        return jsonify(id=cid,message='Relevé envoyé. Il sera visible après validation.'), 201

    @app.get('/api/contributions/<int:cid>/photo')
    def photo(cid):
        with db() as conn:
            row = conn.execute('SELECT * FROM contributions WHERE id=?', (cid,)).fetchone()
        current = user()
        if not row or not row['proof'] or not (is_admin() or current and row['user_id']==current['id']):
            return error('Photo introuvable.',404)
        response = send_file(root / 'proofs' / row['proof'], mimetype='image/jpeg')
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    @app.get('/api/admin/contributions')
    def moderation_list():
        if not is_admin():
            return error('Accès administrateur requis.',401)
        with db() as conn:
            rows = conn.execute('SELECT * FROM contributions ORDER BY id DESC LIMIT 1000').fetchall()
        return jsonify(contributions=[{k:r[k] for k in r.keys() if k not in ('proof_hash','fingerprint')} for r in rows])

    @app.post('/api/reports')
    def report_price():
        current = user()
        if not current:
            return error('Connectez-vous pour envoyer un signalement.', 401)
        if not csrf_ok():
            return error('Session expirée. Actualisez la page.', 403)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error('Signalement invalide.')
        article, store, reason, comment = (data.get(key, '') for key in ('article','store','reason','comment'))
        if not all(isinstance(value,str) for value in (article,store,reason,comment)):
            return error('Signalement invalide.')
        if not article.strip() or len(article)>200 or not store.strip() or len(store)>120 or len(comment)>2000 or reason not in ('wrong_price','unavailable','wrong_format','other'):
            return error('Vérifiez les informations du signalement.')
        with db() as conn:
            duplicate = conn.execute("SELECT id FROM reports WHERE user_id=? AND article=? AND store=? AND reason=? AND status='pending'",(current['id'],article.strip(),store.strip(),reason)).fetchone()
            if duplicate:
                return error('Vous avez déjà signalé cette erreur. Elle est en attente de vérification.',409)
            conn.execute('INSERT INTO reports(user_id,article,store,reason,comment,created_at) VALUES(?,?,?,?,?,?)',(current['id'],article.strip(),store.strip(),reason,comment.strip(),now()))
        return jsonify(message='Signalement envoyé à l’administration. Merci !'),201

    @app.get('/api/admin/reports')
    def report_list():
        if not is_admin():
            return error('Accès administrateur requis.',401)
        with db() as conn:
            rows=conn.execute('SELECT id,article,store,reason,comment,created_at,status FROM reports ORDER BY id DESC LIMIT 1000').fetchall()
        return jsonify(reports=[dict(row) for row in rows])

    @app.post('/api/admin/reports/<int:rid>/resolve')
    def resolve_report(rid):
        if not is_admin():
            return error('Accès administrateur requis.',401)
        with db() as conn:
            result=conn.execute("UPDATE reports SET status='resolved' WHERE id=?",(rid,))
            if not result.rowcount:
                return error('Signalement introuvable.',404)
        return jsonify(message='Signalement traité. Corrigez le prix dans la gestion des prix si nécessaire.')

    @app.post('/api/admin/contributions/<int:cid>/decision')
    def decide(cid):
        if not is_admin():
            return error('Accès administrateur requis.',401)
        data = request.get_json(silent=True) or {}
        if not isinstance(data,dict):
            return error('Décision invalide.')
        choice, note = data.get('decision'), data.get('note','')
        if choice not in ('approved','rejected') or not isinstance(note,str) or len(note)>2000:
            return error('Décision invalide.')
        if choice=='rejected' and not note.strip():
            return error('Expliquez le refus au contributeur.')
        with db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT * FROM contributions WHERE id=?',(cid,)).fetchone()
            if not row:
                return error('Relevé introuvable.',404)
            if row['status']==choice:
                return jsonify(message='Décision déjà appliquée.')
            if row['status']=='rejected':
                return error('Un relevé refusé est clôturé. Le contributeur peut envoyer un nouveau relevé.',409)
            if choice=='approved' and row['observed_at'] < (date.today()-timedelta(days=30)).isoformat():
                return error('Ce relevé a plus de 30 jours : demandez un prix récent.')
            conn.execute('UPDATE contributions SET status=?,review_note=?,reviewed_at=? WHERE id=?', (choice,note.strip(),now(),cid))
            conn.execute('INSERT INTO decisions(contribution_id,decision,note,created_at) VALUES(?,?,?,?)',(cid,choice,note.strip(),now()))
            if choice=='approved':
                conn.execute('INSERT OR IGNORE INTO point_ledger(user_id,contribution_id,kind,amount,created_at) VALUES(?,?,?,?,?)',(row['user_id'],cid,'approval',10,now()))
            elif row['status']=='approved':
                conn.execute('INSERT OR IGNORE INTO point_ledger(user_id,contribution_id,kind,amount,created_at) VALUES(?,?,?,?,?)',(row['user_id'],cid,'reversal',-10,now()))
        return jsonify(message='Décision enregistrée. La recherche publique est actualisée.')

    return public_prices