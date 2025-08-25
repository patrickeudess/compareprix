from flask import Flask, render_template, request, jsonify, send_from_directory
import json
import os
from datetime import datetime

app = Flask(__name__, static_folder='static')

# Chemin vers le fichier JSON des données
DATA_FILE = 'data/articles.json'

def load_articles():
    """Charge les données des articles depuis le fichier JSON"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_articles(articles):
    """Sauvegarde les données des articles dans le fichier JSON"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

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
    """Traite les signalements d'utilisateurs"""
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
        
        # Validation des données requises
        if not all([product_name, supermarket, current_price, new_price, feedback_type]):
            return jsonify({
                'status': 'error',
                'message': 'Tous les champs obligatoires doivent être remplis'
            })
        
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
                    
                    # Générer un nom de fichier unique
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"feedback_{timestamp}_{photo.filename}"
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
            'current_price': int(current_price),
            'new_price': int(new_price),
            'price_difference': int(new_price) - int(current_price),
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
        
    except Exception as e:
        print(f"Erreur lors du traitement du feedback: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Erreur lors du traitement du signalement'
        })

@app.route('/api/feedback', methods=['GET'])
def get_feedback():
    """Récupère tous les signalements (pour l'équipe)"""
    try:
        feedback_list = load_feedback()
        return jsonify({
            'status': 'success',
            'feedback': feedback_list
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        })

@app.route('/api/feedback/<feedback_id>', methods=['PUT'])
def update_feedback(feedback_id):
    """Met à jour le statut d'un signalement (pour l'équipe)"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        review_notes = data.get('review_notes', '')
        reviewer = data.get('reviewer', 'Équipe')
        
        feedback_list = load_feedback()
        
        # Trouver et mettre à jour le feedback
        for feedback in feedback_list:
            if feedback['id'] == feedback_id:
                feedback['status'] = new_status
                feedback['review_notes'] = review_notes
                feedback['reviewed_by'] = reviewer
                feedback['review_date'] = datetime.now().isoformat()
                break
        
        # Sauvegarder les modifications
        save_feedback_list(feedback_list)
        
        return jsonify({
            'status': 'success',
            'message': 'Signalement mis à jour'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erreur: {str(e)}'
        })

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
    
    app.run(debug=True, host='0.0.0.0', port=5000)
