import requests
from bs4 import BeautifulSoup # type: ignore
import json
from datetime import date
import time
import random
import re
from urllib.parse import urljoin
import os

class JumiaScraper:
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
                '[data-testid="product-name"]'
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
                '.prc'
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
                '.prd img'
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
    
    def scrape_food_products(self, max_pages=5):
        """Scrape les produits alimentaires de Jumia"""
        products = []
        
        # Catégories alimentaires à scraper
        food_categories = [
            '/supermarche/',
            '/alimentation/',
            '/boissons/',
            '/fruits-legumes/',
            '/viandes-poissons/',
            '/produits-laitiers/',
            '/epicerie/'
        ]
        
        for category in food_categories:
            print(f"Scraping de la catégorie: {category}")
            
            for page in range(1, max_pages + 1):
                try:
                    if page == 1:
                        url = f"{self.base_url}{category}"
                    else:
                        url = f"{self.base_url}{category}?page={page}"
                    
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
                        '[data-testid="product-link"]'
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
                    for i, product_url in enumerate(product_links[:10]):  # Limiter à 10 produits par page
                        print(f"    Produit {i+1}/{min(len(product_links), 10)}: {product_url}")
                        
                        product_data = self.get_product_details(product_url)
                        if product_data and product_data['product_name'] and product_data['price']:
                            products.append(product_data)
                            print(f"      ✓ {product_data['product_name']} - {product_data['price']} FCFA")
                        
                        # Pause entre les requêtes
                        time.sleep(random.uniform(1, 3))
                    
                    # Pause entre les pages
                    time.sleep(random.uniform(2, 5))
                    
                except Exception as e:
                    print(f"Erreur lors du scraping de la page {page}: {e}")
                    continue
        
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
        product_name_lower = product_name.lower()
        
        # Liquides
        if any(word in product_name_lower for word in ['lait', 'huile', 'jus', 'eau', 'soda', 'bière', 'vin']):
            return 'L'
        
        # Poids
        if any(word in product_name_lower for word in ['riz', 'sucre', 'farine', 'pâtes', 'céréales', 'chocolat']):
            return 'kg'
        
        # Fruits et légumes
        if any(word in product_name_lower for word in ['tomate', 'pomme', 'banane', 'orange', 'mangue']):
            return 'kg'
        
        # Par défaut
        return 'unité'

def main():
    print("🛒 Scraping des produits alimentaires Jumia Côte d'Ivoire")
    print("=" * 60)
    
    scraper = JumiaScraper()
    
    # Scraper les produits
    products = scraper.scrape_food_products(max_pages=3)
    
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
        print(f"   - Prix moyen: {sum(p['price'] for p in products if p['price']) // len(products)} FCFA")
        print(f"   - Produits avec images: {sum(1 for p in products if p['image_url'])}")
        
        # Afficher quelques exemples
        print("\n📝 Exemples de produits:")
        for i, product in enumerate(products[:5]):
            print(f"   {i+1}. {product['product_name']} - {product['price']} FCFA")
    
    else:
        print("❌ Aucun produit trouvé")

if __name__ == "__main__":
    main()
