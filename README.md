# ComparePrix

ComparePrix permet de consulter des prix sans compte et de proposer des relevés avec un compte contributeur.

## Parcours disponibles

- `/` : recherche publique, filtre par magasin, prix du format et prix par unité de référence pour les contributions.
- `/compte` ou `/compte.html` : création de compte, connexion, suivi des contributions et points.
- `/contribuer` ou `/contribuer.html` : formulaire produit, marque, variante, quantité, unité, prix FCFA, magasin, ville/quartier/boutique, date, photo facultative.
- `/admin` : gestion des prix manuels ; lien vers la modération.
- `/admin/contributions` : contrôle de la preuve privée, acceptation, refus motivé ou retrait de validation.

Un utilisateur peut préparer son brouillon avant de se connecter. Seul l’envoi exige un compte. Le brouillon est enregistré localement sur son navigateur, sans photo ; un bouton permet de l’effacer.

## Installation serveur

Python 3.10 ou supérieur :

```bash
pip install -r requirements.txt
python app.py
```

Ouvrir http://localhost:5000. Pour un hébergement public, utiliser un serveur WSGI avec HTTPS et un disque persistant ; le serveur de développement Flask sert à l’aperçu local.

Configurer :
- `COMPAREPRIX_ADMIN_TOKEN` : secret administrateur, demandé dans l’interface ; jamais dans le dépôt.
- `COMPAREPRIX_SECRET_KEY` : clé stable de session en production. En local, une clé est créée dans `data/.session-secret`.
- `COMPAREPRIX_COOKIE_SECURE=true` : sur un serveur HTTPS.
- `COMPAREPRIX_DATA_DIR` : dossier persistant pour la base collaborative et les photos ; par défaut `data`.

Les prix manuels utilisent encore `data/articles.json`. Les comptes, observations, décisions et mouvements de points sont dans `community.sqlite3`. Les fichiers de preuve sont dans `proofs/`. Sauvegarder ces données privées avec la clé de session et ne pas les servir comme fichiers publics. La base et les preuves ne doivent jamais être publiées sur GitHub.

## Validation

- Prix entier positif en FCFA, quantité positive, unité explicite.
- Date dans les 30 derniers jours, aucune date future.
- Détection du même relevé et de la réutilisation exacte d’une photo réencodée.
- Photos JPG/PNG de 5 Mo maximum et 25 mégapixels maximum, réencodées pour retirer EXIF et géolocalisation.
- Relevés en attente invisibles dans la recherche ; validation humaine obligatoire.
- Historique conservé ; le relevé accepté le plus récent pour chaque produit/marque/variante/format/magasin/lieu est publié.
- Relevés publics retirés des résultats après 30 jours depuis leur observation ; ils restent dans l’historique.
- 10 points par acceptation, crédités une seule fois ; retrait de validation : mouvement de -10 points une seule fois. Aucune valeur monétaire.
- Auteur et photo accessibles uniquement à l’auteur et à l’administration ; aucun email, pseudo ou photo dans le flux public.
- Les prix manuels sans date sont signalés comme tels.

Les mots de passe sont hachés. Les opérations de compte et de contribution utilisent une session et un jeton CSRF ; les endpoints administrateur utilisent le jeton Bearer. Les réponses privées ne sont pas mises en cache. L’ancien endpoint anonyme `/submit_feedback` est retiré (HTTP 410) au profit du parcours connecté.

## Collecter les premiers prix

`data/fiche_collecte.xlsx` est la fiche à emporter en magasin : 30 produits courants × 3 magasins, avec règles de relevé (onglet « Lisez-moi »), listes déroulantes et contrôles de saisie (onglet « Saisie »), et suivi d’avancement par magasin (onglet « Suivi »). Pour la régénérer avec d’autres magasins ou produits : `python tools/build_fiche.py --stores "Carrefour,Casino"` (nécessite `pip install -r requirements-dev.txt`).

Parcours : remplir `prix` et `date_releve` (une ligne sans prix est ignorée, un produit absent reste vide) → *Enregistrer sous* CSV depuis l’onglet « Saisie » → `/admin` → Importer un CSV (simulation d’abord ; tout est refusé si une seule ligne est invalide). Les prix avec espaces ou « FCFA » et les dates `JJ/MM/AAAA` d’Excel français sont acceptés ; un prix non entier n’est jamais arrondi. Les prix importés sont « à vérifier » jusqu’à validation dans `/admin`.

## Vérification d’email et récupération du mot de passe

Facultatives : l’inscription par téléphone reste immédiate. Un email vérifié (code à 6 chiffres, valable 15 minutes, 5 essais) permet de récupérer le mot de passe depuis « Mot de passe oublié ? ». Sans SMTP configuré, la fonction est masquée et inactive.

- `COMPAREPRIX_SMTP_HOST`, `COMPAREPRIX_SMTP_FROM` (obligatoires pour activer), `COMPAREPRIX_SMTP_PORT` (587 par défaut), `COMPAREPRIX_SMTP_USER`, `COMPAREPRIX_SMTP_PASSWORD`.
- `COMPAREPRIX_SMTP_SECURITY` : `starttls` (défaut), `ssl` (port 465) ou `none` (relais local uniquement).
- `COMPAREPRIX_REQUIRE_VERIFIED_EMAIL=true` : exige un email vérifié pour envoyer un prix (désactivé par défaut pour ne pas freiner les contributions ; sans effet si SMTP n’est pas configuré).

Le code n’est jamais stocké en clair (empreinte HMAC) ; la demande de récupération répond toujours de la même façon, qu’un compte existe ou non. Les limites d’envoi sont en mémoire par processus (voir `ratelimit.py`). Une réinitialisation de mot de passe déconnecte toutes les sessions ouvertes du compte. Un `COMPAREPRIX_SMTP_SECURITY` inconnu désactive l’envoi d’email (jamais de repli sans chiffrement). Un SMS n’est pas fourni : il exige un compte payant chez un fournisseur.

## GitHub Pages

GitHub Pages ne peut pas exécuter Flask ni stocker des comptes. Le site statique reste une démonstration avec des pages de compte et de saisie qui signalent l’absence du serveur. Le parcours complet fonctionne sur la version Flask. Ne pas annoncer les inscriptions comme disponibles sur GitHub Pages seul.

## Limites de cette première version

Pas encore d’OCR, de publication automatique, de panier comparatif ou de conversion monétaire des points. La modération doit vérifier la preuve et l’équivalence des produits. Les prix ne garantissent pas la disponibilité en magasin. Les limites d’authentification utilisent l’adresse IP vue par Flask ; configurer le proxy explicitement lors de l’hébergement.

## Logos

Chargement depuis les sites officiels avec `referrerpolicy="no-referrer"` ; le nom du magasin reste affiché si le logo est inaccessible.

- Carrefour : https://carrefour.ci/wp-content/uploads/2023/08/carrefour-ci-logo.svg
- Cap Sud : https://groupeprosuma.com/wp-content/uploads/2022/10/logo-cap-sud-mini.png
- Casino : https://groupeprosuma.com/wp-content/uploads/2020/12/logo-casno-supermarche-mini.png

- **GitHub Pages** n'héberge que des fichiers statiques : `index.html` à la racine est la page publique, maintenue à part. Il ne peut pas exécuter l'application Flask. `python tools/build_demo.py` génère en plus une démonstration interactive complète (prix fictifs) dans `build/demo.html`.
- Pour l'application complète (recherche, administration, base de données) : voir **[DEPLOIEMENT.md](DEPLOIEMENT.md)** (VPS + Docker, PythonAnywhere).
