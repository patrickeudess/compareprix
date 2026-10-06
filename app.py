from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
import json
import os
from datetime import datetime
import secrets
import tempfile
from urllib.parse import urlsplit

app = Flask(__name__, static_folder='static')

# Chemin vers le fichier JSON des données
DATA_FILE = 'data/articles.json'
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

def load_manual_articles():
    """Charge les données des articles depuis le fichier JSON"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_articles():
    articles = [dict(value, source='Prix sans date', date_releve=None) for value in load_manual_articles()]
    return articles + load_community_prices()

def save_articles(articles):
    """Sauvegarde les données de manière atomique pour préserver le fichier en cas d'erreur."""
    data_path = os.path.abspath(DATA_FILE)
    data_dir = os.path.dirname(data_path)
    os.makedirs(data_dir, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(prefix='.articles-', suffix='.tmp', dir=data_dir)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary_path, data_path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def validate_admin_article(value):
    """Valide et normalise un prix saisi depuis l'espace administrateur."""
    if not isinstance(value, dict):
        return None, 'Chaque prix doit être un objet JSON'
    article = value.get('article')
    supermarket = value.get('supermarche')
    unit = value.get('unite', 'unité')
    if not isinstance(article, str) or not article.strip() or len(article.strip()) > 200:
        return None, 'Le nom de l’article est obligatoire (200 caractères maximum)'
    if not isinstance(supermarket, str) or not supermarket.strip() or len(supermarket.strip()) > 120:
        return None, 'Le magasin est obligatoire (120 caractères maximum)'
    if isinstance(value.get('prix'), bool) or not isinstance(value.get('prix'), int) or value['prix'] < 1 or value['prix'] > 100000000:
        return None, 'Le prix doit être un entier entre 1 et 100 000 000 FCFA'
    if not isinstance(unit, str) or len(unit.strip()) > 40:
        return None, 'Le format doit contenir au plus 40 caractères'

    normalized = {
        'article': article.strip(),
        'supermarche': supermarket.strip(),
        'prix': value['prix'],
        'unite': unit.strip() or 'unité'
    }
    for field in ('url', 'image_url'):
        url = value.get(field, '')
        if not isinstance(url, str) or len(url) > 2048:
            return None, 'Les liens doivent contenir au plus 2 048 caractères'
        url = url.strip()
        if url:
            try:
                parsed = urlsplit(url)
                if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
                    return None, 'Les liens doivent commencer par http:// ou https://'
            except ValueError:
                return None, 'Un lien est invalide'
        normalized[field] = url
    return normalized, None

@app.route('/admin')
def admin_dashboard():
    """Page de gestion des produits; les données restent protégées par les API Bearer."""
    return render_template('admin.html')


@app.route('/api/admin/articles', methods=['GET', 'PUT'])
def manage_articles():
    """Liste et remplace les prix depuis le tableau administrateur authentifié."""
    if not is_feedback_admin():
        return admin_auth_error()
    if request.method == 'GET':
        try:
            return jsonify({'status': 'success', 'articles': load_manual_articles()})
        except Exception:
            app.logger.exception('Erreur lors de la lecture des articles')
            return jsonify({'status': 'error', 'message': 'Erreur lors de la lecture des prix'}), 500

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('articles'), list):
        return jsonify({'status': 'error', 'message': 'La liste des prix est invalide'}), 400
    if len(data['articles']) > 5000:
        return jsonify({'status': 'error', 'message': 'La liste dépasse la limite de 5 000 prix'}), 400

    normalized = []
    for index, value in enumerate(data['articles']):
        article, error = validate_admin_article(value)
        if error:
            return jsonify({'status': 'error', 'message': f'Prix {index + 1} : {error}'}), 400
        normalized.append(article)
    try:
        save_articles(normalized)
        return jsonify({'status': 'success', 'articles': normalized})
    except Exception:
        app.logger.exception('Erreur lors de l’enregistrement des prix')
        return jsonify({'status': 'error', 'message': 'Erreur lors de l’enregistrement des prix'}), 500


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
    
    articles = load_articles()
    results = []
    
    for article in articles:
        if search_term in article['article'].lower():
            results.append(article)
    
    return jsonify({'results': results})

@app.route('/api/articles')
def get_all_articles():
    """API pour récupérer tous les articles (pour debug)"""
    articles = load_articles()
    return jsonify(articles)

@app.route('/api/articles/<article_name>')
def get_article(article_name):
    """API pour récupérer un article spécifique"""
    articles = load_articles()
    results = [a for a in articles if article_name.lower() in a['article'].lower()]
    return jsonify(results)

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
        return jsonify(articles)
    elif format == 'csv':
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Article', 'Supermarché', 'Prix (FCFA)', 'Unité', 'URL', 'Image URL'])
        
        for article in articles:
            writer.writerow([
                article['article'],
                article['supermarche'],
                article['prix'],
                article.get('unite', 'unité'),
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
    return jsonify({'message': 'Utilisez la page Proposer un prix avec votre compte contributeur.'}), 410

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
        
        feedback_list = load_feedback()
        
        # Trouver et mettre à jour le feedback
        feedback_found = False
        for feedback in feedback_list:
            if feedback['id'] == feedback_id:
                feedback_found = True
                feedback['status'] = new_status
                feedback['review_notes'] = review_notes
                feedback['reviewed_by'] = reviewer
                feedback['review_date'] = datetime.now().isoformat()
                break
        
        if not feedback_found:
            return jsonify({'status': 'error', 'message': 'Signalement introuvable'}), 404
        # Sauvegarder les modifications
        save_feedback_list(feedback_list)
        
        return jsonify({
            'status': 'success',
            'message': 'Signalement mis à jour'
        })
        
    except Exception:
        app.logger.exception('Erreur lors de la mise à jour du signalement')
        return jsonify({'status': 'error', 'message': 'Erreur lors de la mise à jour du signalement'}), 500

def generate_feedback_id():
    """Génère un ID unique pour le feedback"""
    import hashlib
    import os
    timestamp = datetime.now().isoformat()
    random_component = os.urandom(8).hex()
    return hashlib.md5(f"{timestamp}{random_component}".encode()).hexdigest()[:12]

def save_feedback(feedback_entry):
    """Sauvegarde un nouveau feedback"""
    feedback_file = 'data/user_feedback.json'
    
    # Charger les feedbacks existants
    feedback_list = load_feedback()
    
    # Ajouter le nouveau feedback
    feedback_list.append(feedback_entry)
    
    # Sauvegarder
    save_feedback_list(feedback_list)

def load_feedback():
    """Charge tous les feedbacks"""
    feedback_file = 'data/user_feedback.json'
    
    if os.path.exists(feedback_file):
        with open(feedback_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_feedback_list(feedback_list):
    """Sauvegarde la liste des feedbacks"""
    feedback_file = 'data/user_feedback.json'
    
    # Créer le dossier si nécessaire
    os.makedirs(os.path.dirname(feedback_file), exist_ok=True)
    
    with open(feedback_file, 'w', encoding='utf-8') as f:
        json.dump(feedback_list, f, ensure_ascii=False, indent=2)

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

from collaboration import register_collaboration
load_community_prices = register_collaboration(app, is_feedback_admin)

if __name__ == '__main__':
    # Créer des données d'exemple si le fichier n'existe pas
    if not os.path.exists(DATA_FILE):
        sample_data = [
            {"article": "Riz Basmati", "supermarche": "Carrefour", "prix": 500, "unite": "kg"},
            {"article": "Riz Basmati", "supermarche": "Cap Sud", "prix": 520, "unite": "kg"},
            {"article": "Riz Basmati", "supermarche": "Casino", "prix": 480, "unite": "kg"},
            {"article": "Huile d'Olive", "supermarche": "Carrefour", "prix": 1200, "unite": "L"},
            {"article": "Huile d'Olive", "supermarche": "Cap Sud", "prix": 1150, "unite": "L"},
            {"article": "Huile d'Olive", "supermarche": "Casino", "prix": 1250, "unite": "L"},
            {"article": "Pâtes Spaghetti", "supermarche": "Carrefour", "prix": 180, "unite": "kg"},
            {"article": "Pâtes Spaghetti", "supermarche": "Cap Sud", "prix": 175, "unite": "kg"},
            {"article": "Pâtes Spaghetti", "supermarche": "Casino", "prix": 190, "unite": "kg"},
            {"article": "Lait", "supermarche": "Carrefour", "prix": 120, "unite": "L"},
            {"article": "Lait", "supermarche": "Cap Sud", "prix": 125, "unite": "L"},
            {"article": "Lait", "supermarche": "Casino", "prix": 118, "unite": "L"},
            {"article": "Pain", "supermarche": "Carrefour", "prix": 85, "unite": "unité"},
            {"article": "Pain", "supermarche": "Cap Sud", "prix": 90, "unite": "unité"},
            {"article": "Pain", "supermarche": "Casino", "prix": 82, "unite": "unité"}
        ]
        save_articles(sample_data)
    
    app.run(debug=os.environ.get('FLASK_DEBUG', '').lower() == 'true', host='0.0.0.0', port=int(os.environ.get('PORT', '5000')))


