import io
import re

from flask import Flask, render_template, request, jsonify, send_from_directory, g
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
import json
import os
from datetime import datetime
import secrets

import db
from online_prices import apply_updates
from pricing import freshness, enrich_results, unit_stats, store_price_index, validate_article, normalize_key
from backup_db import create_backup
import import_prices
from uploads import MAX_IMAGE_BYTES, detect_image_extension
from ratelimit import SlidingWindowLimiter

app = Flask(__name__, static_folder='static')

# Derrière N reverse-proxies de confiance (Nginx, Caddy, load balancer...), mettre
# COMPAREPRIX_TRUSTED_PROXIES=N pour que request.remote_addr soit l'IP du client (limiteur de débit).
# Par défaut 0 : on ne fait JAMAIS confiance à X-Forwarded-For, sinon un client pourrait
# usurper son IP et contourner la limitation.
_TRUSTED_PROXIES = int(os.environ.get('COMPAREPRIX_TRUSTED_PROXIES', '0'))
if _TRUSTED_PROXIES > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=_TRUSTED_PROXIES, x_proto=_TRUSTED_PROXIES, x_host=_TRUSTED_PROXIES)

# Chemin vers le fichier JSON des données
# Base SQLite : voir db.py (chemin via COMPAREPRIX_DB, défaut data/compareprix.db)
db.init_db()

# Limite des signalements publics par adresse IP (par processus, cf. ratelimit.py)
FEEDBACK_LIMITER = SlidingWindowLimiter(
    int(os.environ.get('COMPAREPRIX_FEEDBACK_LIMIT', '10')),
    int(os.environ.get('COMPAREPRIX_FEEDBACK_WINDOW', '3600')))
MAX_FEEDBACK_PHOTO_BYTES = MAX_IMAGE_BYTES
ALLOWED_FEEDBACK_STATUSES = {'pending_review', 'approved', 'rejected', 'in_progress'}
app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024

def is_feedback_admin():
    """Valide le jeton administrateur sans comparaison en temps variable."""
    expected = os.environ.get('COMPAREPRIX_ADMIN_TOKEN', '')
    header = request.headers.get('Authorization', '')
    provided = header[7:].strip() if header.lower().startswith('bearer ') else ''
    if not expected or not provided:
        return False
    try:
        return secrets.compare_digest(provided.encode('utf-8'), expected.encode('utf-8'))
    except UnicodeError:
        return False

# Essais de jeton erronés par IP : freine une devinette du jeton (par processus, cf. ratelimit.py)
ADMIN_FAIL_LIMITER = SlidingWindowLimiter(20, 600)

def admin_auth_error():
    allowed, retry_after = ADMIN_FAIL_LIMITER.check(request.remote_addr or 'inconnu')
    if not allowed:
        response = jsonify({'status': 'error', 'message': 'Trop de tentatives, réessayez plus tard'})
        response.status_code = 429
        response.headers['Retry-After'] = str(retry_after)
        return response
    return jsonify({'status': 'error', 'message': 'Authentification administrateur requise'}), 401

def load_articles():
    """Prix courants (dernier relevé par produit et supermarché), avec le cache des prix en ligne
    (online_prices) et les contributions validées de la communauté (collaboration)."""
    return apply_updates(db.list_current()) + load_community_prices()

def with_freshness(article):
    """Ajoute la fraîcheur du relevé (recente / perimee / inconnue / exemple)."""
    level, age = freshness(article)
    return {**article, 'fraicheur': level, 'age_jours': age}

def present(articles):
    """Prépare des articles pour l'API : fraîcheur, prix unitaire, meilleur prix, prix aberrants."""
    return enrich_results([with_freshness(a) for a in articles])

@app.before_request
def _new_csp_nonce():
    g.csp_nonce = secrets.token_urlsafe(16)

@app.context_processor
def _inject_csp_nonce():
    return {'csp_nonce': g.get('csp_nonce', '')}

@app.after_request
def add_security_headers(response):
    """En-têtes de sécurité. La CSP interdit les scripts inline sans nonce : une injection HTML
    (XSS) ne peut plus exécuter de JavaScript même si un échappement venait à manquer."""
    nonce = g.get('csp_nonce', '')
    response.headers.setdefault('Content-Security-Policy', "; ".join([
        "default-src 'self'",
        f"script-src 'self' 'nonce-{nonce}'",
        "style-src 'self' 'unsafe-inline'",        # la page contient un gros bloc <style> inline
        "img-src 'self' data: blob: https:",   # blob: = photos de signalements chargées par l'admin avec le jeton              # images produits hébergées par les enseignes (https)
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]))
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    # HSTS uniquement si le site est réellement servi en HTTPS (sinon il bloquerait l'accès en HTTP)
    if os.environ.get('COMPAREPRIX_HSTS', '').lower() in ('1', 'true'):
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response

@app.route('/healthz')
def healthz():
    """Sonde de santé (Docker/orchestrateur/CI) : vérifie que la base répond. Aucune donnée sensible."""
    try:
        with db.transaction(write=False) as conn:
            conn.execute('SELECT 1').fetchone()
        return jsonify({'status': 'ok'})
    except Exception:
        app.logger.exception('Healthcheck en échec')
        return jsonify({'status': 'error'}), 503

@app.route('/')
def index():
    """Page d'accueil avec le formulaire de recherche"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search_articles():
    """Recherche les articles par nom"""
    search_term = request.form.get('search_term', '').strip().lower()
    
    if not search_term:
        return jsonify({'error': 'Veuillez entrer un terme de recherche'})
    
    return jsonify({'results': present(apply_updates(db.list_current(search_term)))})

@app.route('/api/articles')
def get_all_articles():
    """API pour récupérer tous les articles (pour debug)"""
    articles = load_articles()
    return jsonify(present(articles))

@app.route('/api/articles/<article_name>')
def get_article(article_name):
    """API pour récupérer un article spécifique"""
    return jsonify(present(apply_updates(db.list_current(article_name))))

@app.route('/api/history/<path:article_name>')
def get_price_history(article_name):
    """Historique complet des relevés d'un article (nom exact), filtrable par ?supermarche="""
    return jsonify(db.price_history(article_name, request.args.get('supermarche')))

@app.route('/api/stats')
def get_stats():
    """Statistiques globales. `supermarkets` = prix AFFICHÉS (historique de l'API) ;
    `prix_unitaires` et `indice_prix_magasin` = comparaison fiable (FCFA/kg, FCFA/L)."""
    articles = present(load_articles())
    
    if not articles:
        return jsonify({'error': 'Aucune donnée disponible'})
    
    reels = [x for x in articles if x['statut'] != 'donnee_exemple']
    # Statistiques par supermarché
    supermarkets = {}
    for article in articles:
        supermarkets.setdefault(article['supermarche'], []).append(article)
    
    stats = {
        'total_articles': len(articles),
        'total_supermarkets': len(supermarkets),
        'donnees_exemple': sum(1 for a in articles if a['statut'] == 'donnee_exemple'),
        # Chiffres affichés sur la page d'accueil : uniquement des relevés réels (jamais les données d'exemple)
        'produits_reels': len({normalize_key(x['article']) for x in reels}),
        'magasins_reels': sorted({x['supermarche'] for x in reels}),
        'dernier_releve': max((x['date_releve'] for x in reels if x['date_releve']), default=None),
        'supermarkets': {},
        'prix_unitaires': unit_stats(articles),
        'indice_prix_magasin': store_price_index(articles),
    }
    
    for supermarket, products in supermarkets.items():
        avg_price = sum(p['prix'] for p in products) // len(products)
        stats['supermarkets'][supermarket] = {
            'count': len(products),
            'avg_price': avg_price,
            'min_price': min(p['prix'] for p in products),
            'max_price': max(p['prix'] for p in products)
        }
    
    return jsonify(stats)

@app.route('/api/export/<format>')
def export_data(format):
    """API pour exporter les données"""
    articles = present(load_articles())
    
    if format == 'json':
        return jsonify(articles)
    elif format == 'csv':
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Article', 'Supermarché', 'Prix (FCFA)', 'Unité', 'Prix unitaire', 'Unité de base', 'Date relevé', 'Source', 'Statut', 'URL', 'Image URL'])
        
        for article in articles:
            writer.writerow([
                article['article'],
                article['supermarche'],
                article['prix'],
                article.get('unite', 'unité'),
                article.get('prix_unitaire') if article.get('prix_unitaire') is not None else '',
                article.get('unite_base') or '',
                article.get('date_releve') or '',
                article.get('source', ''),
                article.get('statut', ''),
                article.get('url', ''),
                article.get('image_url', '')
            ])
        
        output.seek(0)
        return output.getvalue(), 200, {'Content-Type': 'text/csv'}
    else:
        return jsonify({'error': 'Format non supporté'})

@app.route('/api/config')
def get_config():
    """API pour récupérer la configuration"""
    try:
        with open('config/features.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        return jsonify(config)
    except FileNotFoundError:
        return jsonify({'error': 'Configuration non trouvée'})

@app.route('/static/<path:filename>')
def static_files(filename):
    """Servir les fichiers statiques"""
    return send_from_directory('static', filename)

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    """Traite les signalements d'utilisateurs"""
    allowed, retry_after = FEEDBACK_LIMITER.check(request.remote_addr or 'inconnu')
    if not allowed:
        response = jsonify({'status': 'error', 'message': 'Trop de signalements, réessayez plus tard'})
        response.status_code = 429
        response.headers['Retry-After'] = str(retry_after)
        return response
    try:
        # Récupérer les données du formulaire
        product_name = request.form.get('product_name', '').strip()
        supermarket = request.form.get('supermarket', '').strip()
        current_price = request.form.get('current_price', '').strip()
        new_price = request.form.get('new_price', '').strip()
        feedback_type = request.form.get('feedback_type', '').strip()
        user_comment = request.form.get('user_comment', '').strip()
        user_name = request.form.get('user_name', '').strip()
        user_email = request.form.get('user_email', '').strip()
        
        # Valider les champs et les tailles avant de traiter le signalement.
        if not all([product_name, supermarket, current_price, new_price, feedback_type]):
            return jsonify({
                'status': 'error',
                'message': 'Tous les champs obligatoires doivent être remplis'
            }), 400
        if len(product_name) > 200 or len(supermarket) > 120 or len(feedback_type) > 40 or len(user_comment) > 2000 or len(user_name) > 120 or len(user_email) > 254:
            return jsonify({'status': 'error', 'message': 'Un ou plusieurs champs dépassent la longueur autorisée'}), 400
        try:
            current_price_value = int(current_price)
            new_price_value = int(new_price)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': 'Les prix doivent être des nombres entiers positifs'}), 400
        if current_price_value < 0 or new_price_value < 0:
            return jsonify({'status': 'error', 'message': 'Les prix doivent être positifs'}), 400
        
        # Photo facultative : validée sur son CONTENU (octets de signature), pas sur son nom
        photo_path = None
        photo = request.files.get('photo')
        if photo and photo.filename:
            header = photo.stream.read(16)
            photo.stream.seek(0, os.SEEK_END)
            photo_size = photo.stream.tell()
            photo.stream.seek(0)
            extension = detect_image_extension(header)
            if extension is None:
                return jsonify({'status': 'error', 'message': 'La photo doit être une image PNG, JPEG ou GIF valide'}), 400
            if photo_size > MAX_FEEDBACK_PHOTO_BYTES:
                return jsonify({'status': 'error', 'message': 'La photo ne doit pas dépasser 5 Mo'}), 400
            os.makedirs('data/user_photos', exist_ok=True)
            # Nom aléatoire + extension déduite du contenu : le nom envoyé par le client est ignoré
            photo_path = os.path.join('data/user_photos', f"feedback_{secrets.token_hex(16)}.{extension}")
            photo.save(photo_path)
        
        # Créer l'entrée de feedback
        feedback_entry = {
            'id': generate_feedback_id(),
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'product_name': product_name,
            'supermarket': supermarket,
            'current_price': current_price_value,
            'new_price': new_price_value,
            'price_difference': new_price_value - current_price_value,
            'feedback_type': feedback_type,
            'user_comment': user_comment,
            'user_name': user_name or 'Anonyme',
            'user_email': user_email,
            'photo_path': photo_path,
            'status': 'pending_review',
            'reviewed_by': None,
            'review_date': None,
            'review_notes': None
        }
        
        # Sauvegarder le feedback
        save_feedback(feedback_entry)
        
        # Envoyer une notification à l'équipe (optionnel)
        send_feedback_notification(feedback_entry)
        
        return jsonify({
            'status': 'success',
            'message': 'Signalement envoyé avec succès !',
            'feedback_id': feedback_entry['id']
        })
        
    except RequestEntityTooLarge:
        return jsonify({'status': 'error', 'message': 'La requête dépasse la taille maximale autorisée'}), 413
    except Exception:
        app.logger.exception('Erreur lors du traitement du signalement')
        return jsonify({
            'status': 'error',
            'message': 'Erreur lors du traitement du signalement'
        }), 500

# ------------------------------------------------------------------ administration

@app.route('/admin')
def admin_page():
    """Coquille de la page d'administration : aucune donnée ni secret ; le jeton est saisi dans
    le navigateur et envoyé en en-tête Authorization à chaque appel d'API."""
    return render_template('admin.html')

_PHOTO_NAME = re.compile(r'^feedback_[0-9a-f]{32}\.(png|jpg|gif)$')

@app.route('/api/feedback/<feedback_id>/photo')
def feedback_photo(feedback_id):
    """Photo d'un signalement (admin). Le nom vient de la base et est revalidé : pas de traversée de chemin."""
    if not is_feedback_admin():
        return admin_auth_error()
    fb = db.get_feedback(feedback_id)
    name = os.path.basename(fb['photo_path']) if fb and fb['photo_path'] else ''
    if not _PHOTO_NAME.match(name):
        return jsonify({'status': 'error', 'message': 'Photo introuvable'}), 404
    return send_from_directory(os.path.abspath('data/user_photos'), name)

@app.route('/api/observations', methods=['GET'])
def list_observations():
    if not is_feedback_admin():
        return admin_auth_error()
    return jsonify({'status': 'success', 'observations': db.recent_observations(request.args.get('limit', 50, type=int))})

@app.route('/api/observations', methods=['POST'])
def create_observation():
    """Saisie d'un relevé de prix (admin). Retourne aussi un avertissement si le prix est aberrant."""
    if not is_feedback_admin():
        return admin_auth_error()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'status': 'error', 'message': 'Corps JSON invalide'}), 400
    rec = {k: (data.get(k).strip() if isinstance(data.get(k), str) else data.get(k))
           for k in ('article', 'supermarche', 'prix', 'unite', 'date_releve', 'source', 'statut', 'url')}
    if isinstance(rec['prix'], str) and rec['prix'].isdigit():
        rec['prix'] = int(rec['prix'])
    if not rec.get('url'):
        rec.pop('url', None)
    errors = validate_article(rec)
    if errors:
        return jsonify({'status': 'error', 'message': 'Relevé invalide', 'errors': errors}), 400
    with db.transaction() as conn:
        oid, created = db.add_observation(conn, rec)
    # Contrôle immédiat : le prix saisi est-il aberrant par rapport aux autres magasins ?
    same = [a for a in present(db.list_current(rec['article']))
            if normalize_key(a['article']) == normalize_key(rec['article'])]
    mine = next((a for a in same if a['supermarche'].lower() == rec['supermarche'].lower()), None)
    return jsonify({'status': 'success', 'observation_id': oid, 'created': created,
                    'anomalie': mine['anomalie'] if mine else None,
                    'prix_unitaire': mine['prix_unitaire'] if mine else None}), 201 if created else 200

@app.route('/api/observations/<int:observation_id>', methods=['PUT'])
def update_observation(observation_id):
    if not is_feedback_admin():
        return admin_auth_error()
    data = request.get_json(silent=True)
    statut = data.get('statut') if isinstance(data, dict) else None
    if statut not in ('valide', 'a_verifier'):
        return jsonify({'status': 'error', 'message': 'Statut invalide (valide, a_verifier)'}), 400
    if not db.set_observation_status(observation_id, statut):
        return jsonify({'status': 'error', 'message': "Relevé introuvable ou donnée d'exemple"}), 404
    return jsonify({'status': 'success'})

@app.route('/api/observations/<int:observation_id>', methods=['DELETE'])
def delete_observation(observation_id):
    if not is_feedback_admin():
        return admin_auth_error()
    result = db.delete_observation(observation_id)
    if result == 'not_found':
        return jsonify({'status': 'error', 'message': 'Relevé introuvable'}), 404
    if result == 'referenced':
        return jsonify({'status': 'error', 'message': 'Relevé lié à un signalement approuvé : suppression refusée'}), 409
    app.logger.info('Relevé %s supprimé par un administrateur', observation_id)
    return jsonify({'status': 'success'})

MAX_IMPORT_BYTES = 2 * 1024 * 1024

@app.route('/api/observations/import', methods=['POST'])
def import_observations():
    """Import d'un CSV de relevés (admin). `apply=1` écrit (après sauvegarde) ; sinon simulation.
    Même validation et même code que `python import_prices.py`."""
    if not is_feedback_admin():
        return admin_auth_error()
    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'status': 'error', 'message': 'Fichier CSV manquant'}), 400
    raw = upload.stream.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        return jsonify({'status': 'error', 'message': 'Fichier trop volumineux (2 Mo maximum)'}), 413
    try:
        rows, errors, skipped = import_prices.parse_csv(io.StringIO(import_prices.decode_csv(raw)))
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    report = {'status': 'success', 'lignes_valides': len(rows), 'lignes_sans_prix_ignorees': skipped,
              'erreurs': [{'ligne': n, 'erreurs': errs} for n, errs in errors], 'applique': False}
    if errors:  # tout ou rien
        report.update(status='error', message=f"{len(errors)} ligne(s) invalide(s) : rien n'a été écrit")
        return jsonify(report), 400
    apply_now = request.form.get('apply') == '1'
    class _DryRun(Exception):
        pass
    try:
        if apply_now and rows:
            create_backup('data/backups', 'avant_import_web_', keep=30)
        with db.transaction() as conn:
            report['resultat'] = import_prices.apply_rows(conn, rows)
            if not apply_now:
                raise _DryRun()  # simulation : on annule la transaction
    except _DryRun:
        pass
    report['applique'] = apply_now
    return jsonify(report)

@app.route('/api/feedback', methods=['GET'])
def get_feedback():
    """Récupère les signalements; endpoint réservé aux administrateurs."""
    if not is_feedback_admin():
        return admin_auth_error()
    try:
        feedback_list = load_feedback()
        return jsonify({
            'status': 'success',
            'feedback': feedback_list
        })
    except Exception:
        app.logger.exception('Erreur lors de la lecture des signalements')
        return jsonify({'status': 'error', 'message': 'Erreur lors de la lecture des signalements'}), 500

@app.route('/api/feedback/<feedback_id>', methods=['PUT'])
def update_feedback(feedback_id):
    """Met à jour un signalement; endpoint réservé aux administrateurs."""
    if not is_feedback_admin():
        return admin_auth_error()
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'status': 'error', 'message': 'Corps JSON invalide'}), 400
        new_status = data.get('status')
        if new_status not in ALLOWED_FEEDBACK_STATUSES:
            return jsonify({'status': 'error', 'message': 'Statut invalide'}), 400
        review_notes = data.get('review_notes', '')
        reviewer = data.get('reviewer', 'Équipe')
        if not isinstance(review_notes, str) or not isinstance(reviewer, str) or len(review_notes) > 2000 or len(reviewer) > 120:
            return jsonify({'status': 'error', 'message': 'Notes ou nom de réviseur invalides'}), 400
        
        outcome = db.set_feedback_status(feedback_id, new_status, review_notes, reviewer)
        if outcome is None:
            return jsonify({'status': 'error', 'message': 'Signalement introuvable'}), 404
        
        return jsonify({
            'status': 'success',
            'message': 'Signalement mis à jour',
            # Un signalement approuvé crée un nouveau relevé de prix (une seule fois)
            'price_applied': outcome['applied'],
            'observation_id': outcome['observation_id'],
            'price_not_applied_reason': None if outcome['applied'] or new_status != 'approved' else outcome['reason']
        })
        
    except Exception:
        app.logger.exception('Erreur lors de la mise à jour du signalement')
        return jsonify({'status': 'error', 'message': 'Erreur lors de la mise à jour du signalement'}), 500

def generate_feedback_id():
    """Génère un ID unique pour le feedback"""
    import hashlib
    timestamp = datetime.now().isoformat()
    random_component = os.urandom(8).hex()
    return hashlib.md5(f"{timestamp}{random_component}".encode()).hexdigest()[:12]

def save_feedback(feedback_entry):
    """Sauvegarde un nouveau feedback (transaction SQLite : sûr en multi-workers)"""
    db.add_feedback(feedback_entry)

def load_feedback():
    """Charge tous les feedbacks"""
    return db.list_feedback()

def send_feedback_notification(feedback_entry):
    """Envoie une notification à l'équipe (simulation)"""
    # Ici, on pourrait envoyer un email ou une notification WhatsApp
    print("🔔 Nouveau signalement reçu:")
    print(f"   - Produit: {feedback_entry['product_name']}")
    print(f"   - Supermarché: {feedback_entry['supermarket']}")
    print(f"   - Prix actuel: {feedback_entry['current_price']} FCFA")
    print(f"   - Nouveau prix: {feedback_entry['new_price']} FCFA")
    print(f"   - Différence: {feedback_entry['price_difference']} FCFA")
    print(f"   - Type: {feedback_entry['feedback_type']}")
    print(f"   - Utilisateur: {feedback_entry['user_name']}")
    
    if feedback_entry['user_comment']:
        print(f"   - Commentaire: {feedback_entry['user_comment']}")
    
    if feedback_entry['photo_path']:
        print(f"   - Photo: {feedback_entry['photo_path']}")

from collaboration import register_collaboration
load_community_prices = register_collaboration(app, is_feedback_admin)

if __name__ == '__main__':
    # Serveur de DÉVELOPPEMENT, local par défaut. En production : gunicorn (voir Dockerfile).
    app.run(debug=os.environ.get('FLASK_DEBUG', '').lower() == 'true',
            host=os.environ.get('COMPAREPRIX_HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '5000')))
