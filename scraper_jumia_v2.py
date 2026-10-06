import requests
from bs4 import BeautifulSoup # type: ignore # type: ignore
import json
from datetime import date
import time
import random
import re
from urllib.parse import urljoin
import os

class JumiaScraperV2:
    def __init__(self):
        self.base_url = "https://www.jumia.ci"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def explore_site_structure(self):
        """Explore la structure du site Jumia CI pour trouver les bonnes URLs"""
        print("🔍 Exploration de la structure du site Jumia CI...")
        
        try:
            response = self.session.get(self.base_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Chercher les liens de catégories
            category_links = []
            
            # Patterns pour les catégories alimentaires
            food_patterns = [
                'supermarche', 'alimentation', 'boissons', 'fruits', 'legumes',
                'viande', 'poisson', 'laitier', 'epicerie', 'food', 'grocery',
                'supermarket', 'beverages', 'dairy', 'meat', 'fish'
            ]
            
            # Chercher dans les liens de navigation
            nav_selectors = [
                'nav a', '.nav a', '.menu a', '.categories a',
                '[class*="nav"] a', '[class*="menu"] a', '[class*="category"] a'
            ]
            
            for selector in nav_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True).lower()
                    
                    # Vérifier si c'est une catégorie alimentaire
                    if any(pattern in href.lower() or pattern in text for pattern in food_patterns):
                        if href.startswith('/'):
                            full_url = urljoin(self.base_url, href)
                            category_links.append({
                                'url': full_url,
                                'name': link.get_text(strip=True),
                                'href': href
                            })
            
            # Si aucune catégorie trouvée, essayer des URLs communes
            if not category_links:
                common_urls = [
                    '/supermarche/',
                    '/alimentation/',
                    '/boissons/',
                    '/fruits-legumes/',
                    '/viandes-poissons/',
                    '/produits-laitiers/',
                    '/epicerie/',
                    '/food/',
                    '/grocery/',
                    '/supermarket/',
                    '/beverages/',
                    '/dairy/',
                    '/meat/',
                    '/fish/'
                ]
                
                for url in common_urls:
                    category_links.append({
                        'url': urljoin(self.base_url, url),
                        'name': url.strip('/').replace('-', ' ').title(),
                        'href': url
                    })
            
            print(f"📋 Catégories trouvées: {len(category_links)}")
            for cat in category_links:
                print(f"   - {cat['name']}: {cat['url']}")
            
            return category_links
            
        except Exception as e:
            print(f"❌ Erreur lors de l'exploration: {e}")
            return []
    
    def extract_price(self, price_text):
        """Extrait le prix en FCFA depuis le texte"""
        if not price_text:
            return None
            
        # Nettoyer le texte
        price_text = price_text.strip()
        
        # Chercher les patterns de prix
        patterns = [
            r'(\d+(?:\s\d+)*)\s*FCFA',  # 1 500 FCFA
            r'(\d+(?:\s\d+)*)\s*CFA',   # 1 500 CFA
            r'(\d+(?:\s\d+)*)\s*₣',     # 1 500 ₣
            r'(\d+(?:\s\d+)*)',         # 1500
        ]
        
        for pattern in patterns:
            match = re.search(pattern, price_text)
            if match:
                # Extraire les chiffres et les joindre
                price_str = match.group(1).replace(' ', '')
                try:
                    return int(price_str)
                except ValueError:
                    continue
        
        return None
    
    def get_product_details(self, product_url):
        """Récupère les détails d'un produit depuis sa page"""
        try:
            response = self.session.get(product_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Nom du produit
            product_name = ""
            name_selectors = [
                'h1[data-testid="product-title"]',
                'h1.product-title',
                'h1[class*="title"]',
                'h1',
                '.product-name',
                '[data-testid="product-name"]',
                '.prd-name',
                '.name'
            ]
            
            for selector in name_selectors:
                name_elem = soup.select_one(selector)
                if name_elem:
                    product_name = name_elem.get_text(strip=True)
                    break
            
            # Prix
            price = None
            price_selectors = [
                '[data-testid="product-price"]',
                '.product-price',
                '.price',
                '[class*="price"]',
                '.prc',
                '.prc-now',
                '.prc-dsc'
            ]
            
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = self.extract_price(price_text)
                    if price:
                        break
            
            # Image du produit
            image_url = ""
            img_selectors = [
                'img[data-testid="product-image"]',
                '.product-image img',
                '.gallery-image img',
                'img[class*="product"]',
                '.prd img',
                '.img img',
                '.image img'
            ]
            
            for selector in img_selectors:
                img_elem = soup.select_one(selector)
                if img_elem and img_elem.get('src'):
                    image_url = img_elem.get('src')
                    if not image_url.startswith('http'):
                        image_url = urljoin(self.base_url, image_url)
                    break
            
            return {
                'product_name': product_name,
                'price': price,
                'store': 'Jumia',
                'url': product_url,
                'image_url': image_url
            }
            
        except Exception as e:
            print(f"Erreur lors de la récupération du produit {product_url}: {e}")
            return None
    
    def scrape_category(self, category_url, category_name, max_pages=2):
        """Scrape une catégorie spécifique"""
        products = []
        
        for page in range(1, max_pages + 1):
            try:
                if page == 1:
                    url = category_url
                else:
                    # Essayer différents formats de pagination
                    if '?' in category_url:
                        url = f"{category_url}&page={page}"
                    else:
                        url = f"{category_url}?page={page}"
                
                print(f"  Page {page}: {url}")
                
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Trouver les liens des produits
                product_links = []
                link_selectors = [
                    'a[href*="/produit/"]',
                    'a[href*="/product/"]',
                    '.prd a',
                    '.product-item a',
                    '[data-testid="product-link"]',
                    '.card a',
                    '.item a'
                ]
                
                for selector in link_selectors:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href')
                        if href and ('/produit/' in href or '/product/' in href):
                            if not href.startswith('http'):
                                href = urljoin(self.base_url, href)
                            product_links.append(href)
                
                # Supprimer les doublons
                product_links = list(set(product_links))
                
                print(f"    Trouvé {len(product_links)} produits")
                
                # Récupérer les détails de chaque produit
                for i, product_url in enumerate(product_links[:5]):  # Limiter à 5 produits par page
                    print(f"    Produit {i+1}/{min(len(product_links), 5)}: {product_url}")
                    
                    product_data = self.get_product_details(product_url)
                    if product_data and product_data['product_name'] and product_data['price']:
                        products.append(product_data)
                        print(f"      ✓ {product_data['product_name']} - {product_data['price']} FCFA")
                    
                    # Pause entre les requêtes
                    time.sleep(random.uniform(1, 2))
                
                # Pause entre les pages
                time.sleep(random.uniform(2, 3))
                
            except Exception as e:
                print(f"Erreur lors du scraping de la page {page}: {e}")
                continue
        
        return products
    
    def scrape_food_products(self, max_pages=2):
        """Scrape les produits alimentaires de Jumia"""
        products = []
        
        # Explorer la structure du site
        categories = self.explore_site_structure()
        
        if not categories:
            print("❌ Aucune catégorie trouvée, utilisation des URLs par défaut")
            # URLs par défaut à essayer
            default_categories = [
                {'url': 'https://www.jumia.ci/supermarche/', 'name': 'Supermarche'},
                {'url': 'https://www.jumia.ci/food/', 'name': 'Food'},
                {'url': 'https://www.jumia.ci/grocery/', 'name': 'Grocery'}
            ]
            categories = default_categories
        
        for category in categories:
            print(f"\n🛒 Scraping de la catégorie: {category['name']}")
            category_products = self.scrape_category(category['url'], category['name'], max_pages)
            products.extend(category_products)
            
            # Pause entre les catégories
            time.sleep(random.uniform(3, 5))
        
        return products
    
    def save_to_json(self, products, filename='data/jumia_products.json'):
        """Sauvegarde les produits dans un fichier JSON"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ {len(products)} produits sauvegardés dans {filename}")
    
    def convert_to_compareprix_format(self, products):
        """Convertit les données Jumia au format ComparePrix"""
        compareprix_data = []
        
        for product in products:
            # Déterminer l'unité basée sur le nom du produit
            unit = self.determine_unit(product['product_name'])
            
            compareprix_data.append({
                'article': product['product_name'],
                'supermarche': 'Jumia',
                'prix': product['price'],
                'unite': unit,
                'url': product['url'],
                'image_url': product['image_url'],
                'date_releve': date.today().isoformat(),
                'source': 'jumia',
                'statut': 'a_verifier'
            })
        
        return compareprix_data
    
    def determine_unit(self, product_name):
        """Détermine l'unité basée sur le nom du produit"""
        if not product_name:
            return 'unité'
            
        product_name_lower = product_name.lower()
        
        # Liquides
        if any(word in product_name_lower for word in ['lait', 'huile', 'jus', 'eau', 'soda', 'bière', 'vin', 'liquide']):
            return 'L'
        
        # Poids
        if any(word in product_name_lower for word in ['riz', 'sucre', 'farine', 'pâtes', 'céréales', 'chocolat', 'kg', 'gramme']):
            return 'kg'
        
        # Fruits et légumes
        if any(word in product_name_lower for word in ['tomate', 'pomme', 'banane', 'orange', 'mangue', 'fruit', 'légume']):
            return 'kg'
        
        # Par défaut
        return 'unité'

def main():
    print("🛒 Scraping des produits alimentaires Jumia Côte d'Ivoire (v2)")
    print("=" * 70)
    
    scraper = JumiaScraperV2()
    
    # Scraper les produits
    products = scraper.scrape_food_products(max_pages=2)
    
    if products:
        # Sauvegarder les données brutes
        scraper.save_to_json(products, 'data/jumia_products_raw.json')
        
        # Convertir au format ComparePrix
        compareprix_data = scraper.convert_to_compareprix_format(products)
        
        # Sauvegarder au format ComparePrix
        scraper.save_to_json(compareprix_data, 'data/jumia_products.json')
        
        # Afficher un résumé
        print("\n📊 Résumé:")
        print(f"   - Produits trouvés: {len(products)}")
        if products:
            avg_price = sum(p['price'] for p in products if p['price']) // len(products)
            print(f"   - Prix moyen: {avg_price} FCFA")
            print(f"   - Produits avec images: {sum(1 for p in products if p['image_url'])}")
        
        # Afficher quelques exemples
        print("\n📝 Exemples de produits:")
        for i, product in enumerate(products[:5]):
            print(f"   {i+1}. {product['product_name']} - {product['price']} FCFA")
    
    else:
        print("❌ Aucun produit trouvé")
        print("ℹ️ Aucune donnée écrite (jamais de données factices).")

if __name__ == "__main__":
    main()
