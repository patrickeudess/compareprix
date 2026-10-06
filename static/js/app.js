// Fonctionnalités interactives pour ComparePrix

// Gestionnaire d'état global
const AppState = {
    currentSearch: '',
    currentResults: [],
    currentFilter: 'all',
    favorites: JSON.parse(localStorage.getItem('compareprix_favorites') || '[]'),
    
    addToFavorites(product) {
        if (!this.favorites.find(f => f.article === product.article && f.supermarche === product.supermarche)) {
            this.favorites.push(product);
            localStorage.setItem('compareprix_favorites', JSON.stringify(this.favorites));
            showToast('Produit ajouté aux favoris !', 'success');
        }
    },
    
    removeFromFavorites(product) {
        this.favorites = this.favorites.filter(f => 
            !(f.article === product.article && f.supermarche === product.supermarche)
        );
        localStorage.setItem('compareprix_favorites', JSON.stringify(this.favorites));
        showToast('Produit retiré des favoris', 'warning');
    }
};

// Fonction pour afficher des notifications toast
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <span>${getToastIcon(type)}</span>
            <span>${String(message).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}</span>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Afficher le toast
    setTimeout(() => toast.classList.add('show'), 100);
    
    // Masquer le toast après 3 secondes
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => document.body.removeChild(toast), 300);
    }, 3000);
}

function getToastIcon(type) {
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    return icons[type] || icons.info;
}

// Fonction pour trier les résultats
function sortResults(criteria) {
    const results = [...AppState.currentResults];
    
    switch(criteria) {
        case 'price-asc':
            results.sort((a, b) => a.prix - b.prix);
            break;
        case 'price-desc':
            results.sort((a, b) => b.prix - a.prix);
            break;
        case 'name':
            results.sort((a, b) => a.article.localeCompare(b.article));
            break;
        case 'supermarket':
            results.sort((a, b) => a.supermarche.localeCompare(b.supermarche));
            break;
    }
    
    displayResults(results, AppState.currentSearch);
}

// Fonction pour exporter les résultats
function exportResults(format = 'json') {
    const results = AppState.currentResults;
    
    if (format === 'json') {
        const dataStr = JSON.stringify(results, null, 2);
        const dataBlob = new Blob([dataStr], {type: 'application/json'});
        downloadFile(dataBlob, `compareprix_${AppState.currentSearch}_${new Date().toISOString().split('T')[0]}.json`);
    } else if (format === 'csv') {
        const csvContent = convertToCSV(results);
        const dataBlob = new Blob([csvContent], {type: 'text/csv'});
        downloadFile(dataBlob, `compareprix_${AppState.currentSearch}_${new Date().toISOString().split('T')[0]}.csv`);
    }
    
    showToast('Export terminé !', 'success');
}

function convertToCSV(data) {
    const headers = ['Article', 'Supermarché', 'Prix (FCFA)', 'Unité', 'Date relevé', 'Source', 'URL'];
    const csvRows = [headers.join(',')];
    
    data.forEach(item => {
        const row = [
            `"${item.article}"`,
            `"${item.supermarche}"`,
            item.prix,
            `"${item.unite}"`,
            `"${item.date_releve || ''}"`,
            `"${item.source || ''}"`,
            `"${item.url || ''}"`
        ];
        csvRows.push(row.join(','));
    });
    
    return csvRows.join('\n');
}

function downloadFile(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

// Fonction pour partager les résultats
function shareResults() {
    const results = AppState.currentResults;
    const minPrice = Math.min(...results.map(r => r.prix));
    const bestDeal = results.find(r => r.prix === minPrice);
    
    const text = `🔍 Comparaison de prix pour "${AppState.currentSearch}"\n` +
                 `🏆 Meilleur prix: ${bestDeal.article} - ${bestDeal.prix} FCFA chez ${bestDeal.supermarche}\n` +
                 `📊 ${results.length} articles comparés\n` +
                 `🌐 ComparePrix - Comparez intelligemment !`;
    
    if (navigator.share) {
        navigator.share({
            title: `Comparaison ${AppState.currentSearch}`,
            text: text,
            url: window.location.href
        });
    } else {
        // Fallback: copier dans le presse-papiers
        navigator.clipboard.writeText(text).then(() => {
            showToast('Résultats copiés dans le presse-papiers !', 'success');
        });
    }
}

// Fonction pour ajouter des effets visuels
function addParticleEffect() {
    const particlesContainer = document.createElement('div');
    particlesContainer.className = 'particles';
    
    for (let i = 0; i < 20; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.top = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 6 + 's';
        particlesContainer.appendChild(particle);
    }
    
    document.body.appendChild(particlesContainer);
}

// Fonction pour basculer le mode sombre
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('compareprix_dark_mode', isDark);
    showToast(`Mode ${isDark ? 'sombre' : 'clair'} activé`, 'info');
}

// Fonction pour afficher les favoris
function showFavorites() {
    if (AppState.favorites.length === 0) {
        showToast('Aucun favori enregistré', 'warning');
        return;
    }
    
    displayResults(AppState.favorites, 'Favoris');
    showToast(`${AppState.favorites.length} favoris affichés`, 'success');
}

// Fonction pour ajouter des raccourcis clavier
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + K pour focus sur la recherche
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            document.getElementById('searchInput').focus();
        }
        
        // Échap pour effacer la recherche
        if (e.key === 'Escape') {
            document.getElementById('searchInput').value = '';
            document.getElementById('searchInput').blur();
        }
        
        // Ctrl/Cmd + E pour exporter
        if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
            e.preventDefault();
            exportResults('json');
        }
        
        // Ctrl/Cmd + D pour mode sombre
        if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
            e.preventDefault();
            toggleDarkMode();
        }
    });
}

// Fonction pour améliorer l'accessibilité
function setupAccessibility() {
    // Ajouter des attributs ARIA
    const searchInput = document.getElementById('searchInput');
    searchInput.setAttribute('aria-label', 'Rechercher un article');
    searchInput.setAttribute('aria-describedby', 'search-help');
    
    // Ajouter des descriptions pour les lecteurs d'écran
    const searchHelp = document.createElement('div');
    searchHelp.id = 'search-help';
    searchHelp.className = 'sr-only';
    searchHelp.textContent = 'Tapez le nom d\'un article pour comparer les prix';
    searchInput.parentNode.appendChild(searchHelp);
}

// Fonction pour optimiser les performances
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Recherche avec debounce
const debouncedSearch = debounce((searchTerm) => {
    if (searchTerm.length >= 2) {
        searchArticles(searchTerm);
    }
}, 300);

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    // Restaurer les préférences utilisateur
    const darkMode = localStorage.getItem('compareprix_dark_mode') === 'true';
    if (darkMode) {
        document.body.classList.add('dark-mode');
    }
    
    // Ajouter les effets visuels
    addParticleEffect();
    
    // Configurer les raccourcis clavier
    setupKeyboardShortcuts();
    
    // Configurer l'accessibilité
    setupAccessibility();
    
    // Ajouter la recherche en temps réel
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        const value = e.target.value.trim();
        if (value.length >= 2) {
            debouncedSearch(value);
        }
    });
    
    // Afficher les raccourcis clavier
    showToast('💡 Raccourcis: Ctrl+K (recherche), Ctrl+E (export), Ctrl+D (mode sombre)', 'info');
});

// Fonction pour générer des statistiques avancées
function generateAdvancedStats(results) {
    const stats = {
        totalProducts: results.length,
        supermarkets: [...new Set(results.map(r => r.supermarche))],
        priceRange: {
            min: Math.min(...results.map(r => r.prix)),
            max: Math.max(...results.map(r => r.prix)),
            avg: Math.round(results.reduce((sum, r) => sum + r.prix, 0) / results.length)
        },
        bestDeals: results.filter(r => r.prix === Math.min(...results.map(r => r.prix))),
        priceDistribution: {}
    };
    
    // Distribution des prix par supermarché
    stats.supermarkets.forEach(supermarket => {
        const supermarketProducts = results.filter(r => r.supermarche === supermarket);
        stats.priceDistribution[supermarket] = {
            count: supermarketProducts.length,
            avgPrice: Math.round(supermarketProducts.reduce((sum, r) => sum + r.prix, 0) / supermarketProducts.length),
            minPrice: Math.min(...supermarketProducts.map(r => r.prix)),
            maxPrice: Math.max(...supermarketProducts.map(r => r.prix))
        };
    });
    
    return stats;
}
