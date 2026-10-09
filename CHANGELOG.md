# Changelog — ComparePrix

Historique détaillé : `git log`. Ce fichier ne garde que les changements visibles.

## Non publié
- Nom de domaine : procédure complète (`docs/DOMAINE.md`), outil de vérification (`tools/check_domain.py`), mise à jour des pages GitHub Pages (`tools/set_site_url.py`) et redirection vers l'adresse officielle (`COMPAREPRIX_CANONICAL_HOST`, inactive par défaut).
- **Sécurité** : l'ancien signalement anonyme `/submit_feedback` avait été rétabli par erreur (il écrivait en base et sur disque, avec nom, email et photo, sans compte ni consentement). Il renvoie de nouveau **410**, comme l'indique le README. Les signalements déjà en base restent modérables par l'administrateur.
- Compression gzip des fichiers statiques et des réponses de catalogue (÷3 à ÷7 : 11,5 Ko → 1,6 Ko pour `/api/articles` avec 21 produits). Jamais pour les réponses qui portent un jeton ou une session.
- Prix de référence nationaux (plafonds, moyennes) : table, import par fichier avec simulation, correspondance stricte produit + format + zone, affichage sourcé. Rien n'est visible tant que la ligne n'est pas marquée vérifiée.
- Correction : « Meilleur prix par undefined » et « FCFA / undefined » s'affichaient sur tous les prix saisis à la main (le champ lu n'existe que pour les prix en ligne).
- Courriers et contacts pour l'OCPV, le CNLVC, l'ARTCI, un juriste et les fournisseurs de SMS : `docs/COURRIERS.md`.
- Confidentialité : page `/confidentialite`, case de consentement obligatoire à l'inscription, date de consentement enregistrée.
- Photos réduites sur le téléphone avant l'envoi (mesuré : un PNG de 30 Mo et un JPEG de 11 Mo partent à moins de 1 Mo) : moins de données mobiles consommées.
- Étude du contexte ivoirien avec sources : `docs/ETUDE_CONTEXTE_CI.md`.
- Fiche de collecte Excel prête à l'emploi (`data/fiche_collecte.xlsx`, générée par `tools/build_fiche.py`) : règles de relevé, contrôles de saisie, suivi par magasin, colonnes `lieu` et `note`.
- Import CSV plus tolérant aux exports d'Excel français : dates `JJ/MM/AAAA`, prix « 2 500 » ou « 2500 FCFA ». Aucun arrondi.
- Email de récupération facultatif : vérification par code à 6 chiffres et « Mot de passe oublié ? » (voir README, activé seulement si SMTP est configuré).
- Navigation et barre du panier : icônes SVG et barre masquée tant que le panier est vide, désormais aussi dans les gabarits servis par Flask (`templates/`).
- Le statut interne `a_verifier` n'est jamais montré brut : l'utilisateur voit « Prix en ligne · vu le … », « ✓ Validé » ou « À confirmer ».
- Suppression de l'ancien système de collecte (scrapers, WhatsApp, outils de validation, documentation associée) remplacé par le parcours connecté + modération.

## 2.0.0 — 2025-08-23
Refonte de l'interface (mode sombre, filtres par magasin, export JSON/CSV, partage, favoris, statistiques).
