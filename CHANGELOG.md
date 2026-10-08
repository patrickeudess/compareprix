# Changelog — ComparePrix

Historique détaillé : `git log`. Ce fichier ne garde que les changements visibles.

## Non publié
- Email de récupération facultatif : vérification par code à 6 chiffres et « Mot de passe oublié ? » (voir README, activé seulement si SMTP est configuré).
- Navigation et barre du panier : icônes SVG et barre masquée tant que le panier est vide, désormais aussi dans les gabarits servis par Flask (`templates/`).
- Le statut interne `a_verifier` n'est jamais montré brut : l'utilisateur voit « Prix en ligne · vu le … », « ✓ Validé » ou « À confirmer ».
- Suppression de l'ancien système de collecte (scrapers, WhatsApp, outils de validation, documentation associée) remplacé par le parcours connecté + modération.

## 2.0.0 — 2025-08-23
Refonte de l'interface (mode sombre, filtres par magasin, export JSON/CSV, partage, favoris, statistiques).
