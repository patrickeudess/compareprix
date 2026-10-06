from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
import json
import os
from datetime import datetime
import secrets

import db
from pricing import freshness
from ratelimit import SlidingWindowLimiter

app = Flask(__name__, static_folder='static')

# Chemin vers le fichier JSON des données
# Base SQLite : voir db.py (chemin via COMPAREPRIX_DB, défaut data/compareprix.db)
db.init_db()

# Limite des signalements publics par adresse IP (par processus, cf. ratelimit.py)
FEEDBACK_LIMITER = SlidingWindowLimiter(
    int(os.environ.get('COMPAREPRIX_FEEDBACK_LIMIT', '10')),
    int(os.environ.get('COMPAREPRIX_FEEDBACK_WINDOW', '3600')))
MAX_FEEDBACK_PHOTO_BYTES = 5 * 1024 * 1024
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

def admin_auth_error():
    return jsonify({'status': 'error', 'message': 'Authentification administrateur requise'}), 401

def load_articles():
    """Prix courants (dernier relevé par produit et supermarché)"""
    return db.list_current()

def with_freshness(article):
    """Ajoute la fraîcheur du relevé (recente / perimee / inconnue / exemple)."""
    level, age = freshness(article)
    return {**article, 'fraicheur': level, 'age_jours': age}

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
    
    results = [with_freshness(a) for a in db.list_current(search_term)]
    return jsonify({'results': results})

@app.route('/api/articles')
def get_all_articles():
    """API pour récupérer tous les articles (pour debug)"""
    articles = load_articles()
    return jsonify([with_freshness(a) for a in articles])

@app.route('/api/articles/<article_name>')
def get_article(article_name):
    """API pour récupérer un article spécifique"""
    return jsonify([with_freshness(a) for a in db.list_current(article_name)])

@app.route('/api/history/<path:article_name>')
def get_price_history(article_name):
    """Historique complet des relevés d'un article (nom exact), filtrable par ?supermarche="""
    return jsonify(db.price_history(article_name, request.args.get('supermarche')))

@app.route('/api/stats')
def get_stats():
    """API pour récupérer les statistiques globales"""
    articles = load_articles()
    
    if not articles:
        return jsonify({'error': 'Aucune donnée disponible'})
    
    # Statistiques par supermarché
    supermarkets = {}
    for article in articles:
        supermarket = article['supermarche']
        if supermarket not in supermarkets:
            supermarkets[supermarket] = []
        supermarkets[supermarket].append(article)
    
    stats = {
        'total_articles': len(articles),
        'total_supermarkets': len(supermarkets),
        'donnees_exemple': sum(1 for a in articles if a['statut'] == 'donnee_exemple'),
        'supermarkets': {}
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
    articles = load_articles()
    
    if format == 'json':
        return jsonify([with_freshness(a) for a in articles])
    elif format == 'csv':
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Article', 'Supermarché', 'Prix (FCFA)', 'Unité', 'Date relevé', 'Source', 'Statut', 'URL', 'Image URL'])
        
        for article in articles:
            writer.writerow([
                article['article'],
                article['supermarche'],
                article['prix'],
                article.get('unite', 'unité'),
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
        
        # Traitement de la photo si présente
        photo_path = None
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and photo.filename:
                # Vérifier le type de fichier
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
                if '.' in photo.filename and photo.filename.rsplit('.', 1)[1].lower() in allowed_extensions:
                    # Créer le dossier pour les photos si nécessaire
                    os.makedirs('data/user_photos', exist_ok=True)
                    
                    photo.stream.seek(0, os.SEEK_END)
                    photo_size = photo.stream.tell()
                    photo.stream.seek(0)
                    if photo_size > MAX_FEEDBACK_PHOTO_BYTES:
                        return jsonify({'status': 'error', 'message': 'La photo ne doit pas dépasser 5 Mo'}), 400
                    extension = photo.filename.rsplit('.', 1)[1].lower()
                    filename = f"feedback_{secrets.token_hex(16)}.{extension}"
                    photo_path = os.path.join('data/user_photos', filename)
                    
                    # Sauvegarder la photo
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
    except Exception as e:
        app.logger.exception('Erreur lors du traitement du signalement')
        return jsonify({
            'status': 'error',
            'message': 'Erreur lors du traitement du signalement'
        }), 500

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
    print(f"🔔 Nouveau signalement reçu:")
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

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', '').lower() == 'true', host='0.0.0.0', port=int(os.environ.get('PORT', '5000')))
