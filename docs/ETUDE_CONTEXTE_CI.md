# ComparePrix : étude du contexte ivoirien et stratégie affinée

Recherche menée le 9 octobre 2026. **Méthode et limites en fin de document : à lire avant de citer un chiffre.** Chaque affirmation renvoie à sa source ; les points non confirmés sont marqués ⚠️.

## 1. Synthèse : ce que la recherche change

| # | Hypothèse de départ | Ce que disent les sources | Conséquence |
|---|---|---|---|
| 1 | Les marchés et boutiques pèsent plus que les supermarchés | **Confirmé** : petites épiceries 63 % des ventes alimentaires, supermarchés 22 %, hypermarchés 2 % (données 2024) | Une fiche « 3 supermarchés » ne couvre qu'environ un quart des achats. Il faut ajouter marchés et boutiques. |
| 2 | Il n'y a pas de concurrent | **Faux** : Prixci et Promo CI existent déjà | Il faut se différencier clairement (voir §3). |
| 3 | L'argent est le levier pour faire contribuer | **Nuancé** : au Nigeria, 93 % des volontaires s'intéressaient à la donnée, environ 40 % à la récompense | Mêler utilité visible, preuve sociale et petite récompense. |
| 4 | Recruter est le problème | **Faux** : au Nigeria, *retenir* est plus dur que recruter | Prévoir la rétention dès le départ. |
| 5 | L'email suffit pour vérifier les comptes | **Insuffisant** : environ 40 % de la population est en ligne (estimation) et WhatsApp est très utilisé | Passer à un code SMS (≈ 10 à 20 FCFA) puis éventuellement WhatsApp. |
| 6 | Le numéro de téléphone est une donnée comme une autre | **Sensible** : une décision de l'ARTCI le range dans les identifiants soumis à autorisation préalable | Régler la conformité avant un lancement public (voir §6). |
| 7 | 30 jours de validité pour tous les prix | **Trop long pour les produits frais** : l'OCPV publie des relevés hebdomadaires | Validité par catégorie (voir §5). |

## 2. Structure du commerce alimentaire

- **USDA, *Retail Foods Annual* 2025 (données 2024)** : petites épiceries 63 % de part de marché (≈ 4,39 Md USD), supermarchés 22 %, hypermarchés 2 %. La grande distribution représente 15 à 25 % des achats alimentaires. Une grande partie du commerce reste informelle (coût de la formalisation). Les quatre grandes chaînes (Prosuma, Carrefour, Auchan, CDCI) représentent environ 35 % du chiffre d'affaires du commerce de détail (édition 2024, données 2023 ; la source ne précise pas le périmètre exact). [USDA FAS](https://www.fas.usda.gov/data/gain/2025/11/cote-divoire-retail-foods-annual)
- **Team France Export** : environ 85 % de la distribution est informelle, plus de 20 000 boutiques de proximité, environ 35 % des Abidjanais feraient leurs achats mensuels en supermarché (source Nielsen). ⚠️ Les chiffres de la presse (10 % de la valeur des achats en supermarché) ne concordent pas avec ceux-là : ils ne mesurent pas la même chose (part de la valeur, part des transactions, part des clients). [Team France Export](https://www.teamfrance-export.fr/fiche-marche/tech-et-services/retail-et-retailtech/CI) · [Abidjan.net](https://news.abidjan.net/articles/624160/index)
- **AFD, note technique n° 49 (2019)** : à Abidjan, les produits frais passent surtout par des circuits informels et des marchés de quartier, avec de fortes inégalités d'accès entre quartiers, partiellement compensées par la vente ambulante. [AFD](https://www.afd.fr/sites/default/files/2019-02-03-36-15/51-notes-techniques.pdf)
- **Pourquoi les boutiques tiennent** : horaires souples et crédit au client (étude BCG 2022 citée par Agence Ecofin). [Agence Ecofin](https://www.agenceecofin.com/actualites/2611-123779-cote-d-ivoire-les-petites-epiceries-menent-la-course-sur-le-marche-de-la-vente-au-detail)

**Lecture** : un comparateur de supermarchés cible environ un quart des achats alimentaires. Le reste, c'est le marché et la boutique, là où les prix bougent le plus.

## 3. Concurrence et données publiques

| Acteur | Ce que les sources disent | À vérifier |
|---|---|---|
| **Prixci** | Comparateur de prix : scan de produits, prix en direct, « plus de 20 magasins », prix unitaire pour les produits emballés, panier avec alertes. [prixci.com](https://prixci.com/) | ⚠️ Enseignes réellement suivies, méthode de collecte (catalogues en ligne ?), fréquence de mise à jour, propriétaire : **non documentés**. Il faut l'installer et le tester. |
| **Promo CI** | Application de promotions près de soi (géolocalisation), liste de courses partageable via WhatsApp. [App Store](https://apps.apple.com/ci/app/promo-ci-courses-r%C3%A9ducs/id6744569733) | ⚠️ Éditeur et date de lancement non trouvés. |
| QuelPrix | Comparateur surtout électronique et électroménager. [quelprix.ci](https://quelprix.ci/) | Hors épicerie. |
| Adjovan | Courses livrées (marché et supermarché). [Adjovan](https://carrementweb.net/projets/adjovan-application-mobile-de-supermarche/) | Livraison, pas comparaison. |
| **OCPV / Ministère du Commerce** | Relevés **hebdomadaires gratuits** des prix à la consommation des produits vivriers (en FCFA/kg), par marché, avec min-max par marché à Abidjan dans les « notes de conjoncture ». [OCPV](https://www.ocpv-ci.com/) · [Commerce](https://www.commerce.gouv.ci/publications/sous-categorie/21) | ⚠️ Licence de réutilisation à demander. Format PDF. |
| Pouvoirs publics | Grilles tarifaires hebdomadaires pour les vivriers dans 6 marchés (Abidjan, San-Pedro, Bouaké, Yamoussoukro, Man, Korhogo), numéro vert 1343. [Afrique-sur7](https://www.afrique-sur7.fr/cote-divoire-lutte-contre-la-cherte-de-la-vie) | Article non daté dans mes résultats. |

**Positionnement qui reste ouvert** (à confirmer par des tests) : des prix *relevés et vérifiés par la communauté*, **par commune**, couvrant **marchés et boutiques de proximité en plus des supermarchés**, avec prix au kilo ou au litre. Les données publiques de l'OCPV donnent une référence gratuite à comparer.

## 4. Connectivité et paiement

- **ARTCI, T4 2025** (résumé d'un cabinet) : 38,5 M d'abonnements à l'internet mobile, 60,7 M d'abonnements de téléphonie mobile. ⚠️ Ce sont des **cartes SIM**, pas des personnes. [Aris Technologies](https://aristechnologies.ci/blog/rapport-artci-internet-cote-divoire-2025.html)
- **Internautes** : environ 12,8 M, soit environ 40 % de la population (DataReportal, janvier 2025, relayé par Yazi) ; WhatsApp estimé à 10 à 11 M d'utilisateurs. ⚠️ Estimations modélisées, pas des enquêtes. [Yazi](https://www.askyazi.com/useful-data-sources-for-africa/whatsapp-usage-across-africa-key-statistics-insights-for-2025)
- **Smartphones** : 45 % en 2020 (GSMA via WATRA) : donnée ancienne. [WATRA](https://watra.org/cote-divoire/)
- **Coût des données** : environ 1,18 USD le Go en moyenne en 2023 (Cable.co.uk). Part du revenu consacrée au mobile : environ 3,8 % (panier UIT 2025 d'après une source secondaire, contre environ 4,7 % au niveau mondial). [Statista](https://www.statista.com/statistics/1272808/price-for-mobile-data-in-cote-d-ivoire/)
- **Mobile money** : l'ordre de grandeur est de **20 à 26 M de comptes** selon les sources, avec des écarts (définitions différentes). Fin 2024 d'après l'ARTCI (source secondaire) : Orange Money environ 13,8 M, MTN MoMo environ 8,5 M, Moov Money environ 2,9 M ; Wave non comptée. Dans l'UEMOA, seuls 35,1 % des comptes ouverts ont eu une transaction sur 90 jours (BCEAO, fin 2025, via la presse). [BCEAO, rapport 2024](https://www.bceao.int/sites/default/files/2026-03/Rapport%20annuel%20sur%20les%20services%20financiers%20num%C3%A9riques%20dans%20l'UEMOA%20-%202024.pdf)
- **WhatsApp et commerce social** : pas d'enquête formelle sur les achats par WhatsApp ; articles qualitatifs seulement (Ziglôbitha 2025, Les Afriques 2026). [Les Afriques](https://lesafriques.com/en/2026/05/whatsapp-business-in-c-te-d-ivoire-selling-without-a-store/)

**Lecture** : le public connecté est urbain et mobile. Le coût des données justifie la compression des photos (faite : voir CHANGELOG). Le mobile money existe à grande échelle, ce qui rend une petite récompense techniquement possible, mais ses coûts et sa conformité restent à étudier.

## 5. Prix et inflation : où la donnée a de la valeur

- **ANSTAT (IHPC)** : inflation proche de zéro fin 2025 (−0,2 % sur un an en septembre, +0,04 % en novembre). L'alimentaire reste plus mobile : +1,6 % en novembre sur un an ; tubercules, plantains et bananes à cuire +9,3 % en avril 2025 ; poissons −13,9 % en juillet. [ANSTAT, octobre 2025](https://www.anstat.ci/publication-details/fd19942ce06fb6a2f8960f0f8f54e61383d9159f1367e5fbac8660bdb3999ddb6ea2ccb20a0622900f7d823858f2d655a3ddf50e844d1fd17f08f0c15385ecb8JJWZq6bcSCzGC9gfUbr66Oljo1O1Iyz2Xd0uPsS9X1A) · [Horonya Finance](https://www.horonyafinance.com/cote-divoire-inflation-le-niveau-general-davril-2025-en-legere-progression-portee-par-les-produits-alimentaires-et-lenergie/)
- **Écarts entre marchés d'Abidjan** (notes de conjoncture OCPV, 2026) : banane plantain de 360 à 670 F ; gombo frais de 1 250 à 3 330 F entre Abobo et Adjamé. [OCPV, note n° 10](https://ocpv-ci.com/doc/note_de_conjoncture/2026/NOTE_DE_CONJONCTURE_N_10_FEVRIER_2026.pdf)
- La perception de « vie chère » reste forte malgré une inflation officielle faible. [Financial Afrik](https://www.financialafrik.com/2025/07/29/vie-chere-en-cote-divoire-quelles-reponses-des-autorites/)

**Lecture** : l'utilité d'un comparateur est la plus forte là où les écarts entre lieux sont grands (vivriers, frais). Ces produits changent chaque semaine : **valider 30 jours est trop long pour eux**. Proposition : 7 jours pour les vivriers frais, 14 jours pour la viande et le poisson, 30 jours pour l'emballé. Les unités de l'OCPV sont des FCFA/kg : on peut les reprendre telles quelles. ⚠️ Je n'ai trouvé aucune source sur le « tas » ou le « bol » : ces unités sont à mesurer sur le terrain.

## 6. Cadre juridique (à faire valider par un juriste ivoirien)

- **Loi n° 2013-450 du 19 juin 2013** : la déclaration préalable à l'ARTCI est la règle (art. 5). Une **décision de l'ARTCI** applique l'article 7 en citant expressément les **numéros de téléphone** parmi les identifiants soumis à **autorisation préalable**. Un guide de conformité va dans le même sens. ⚠️ Un autre commentaire juridique lit l'article 7 plus étroitement (biométrie) : le texte officiel tranche. [Décision ARTCI (Pont HKB)](https://www.pont-hkb.com/decision-artci-i/) · [Autorité de protection](https://www.autoritedeprotection.ci/lois/) · [Recueil ARTCI](https://renovation.artci.ci/wp-content/uploads/2024/05/RECUEIL-DE-TEXTES-RELATIFS-AUX-TELECOMMUNICATIONS-TIC-ET-A-LA-POSTE-PARTIE-LEGISLATIVE-version-du-02062022.pdf)
- **Transferts hors de Côte d'Ivoire** : soumis à autorisation. ⚠️ Aucune source ne dit clairement si **héberger** sur un serveur étranger (PythonAnywhere) équivaut à un transfert. [Formulaire de transfert ARTCI](https://www.autoritedeprotection.ci/docs/FORMULAIRE-TRANSFERT-DES-DONNEES-1307202.pdf)
- **Droit de la consommation** (loi n° 2016-412) : obligations d'information sur les prix pour les commerçants ; sanctions de 100 000 à 1 800 000 FCFA rapportées par la presse lors d'une opération de contrôle (⚠️ à rattacher à un article précis). [LEAP (PNUE)](https://leap.unep.org/en/countries/ci/national-legislation/loi-ndeg2016-412-du-15-juin-2016-relative-la-consommation)

**Déjà fait dans le code** : page `/confidentialite`, case de consentement explicite à l'inscription, date de consentement enregistrée, photos privées sans métadonnées. **Reste à faire** : valider le texte, déclarer ou faire autoriser le traitement auprès de l'ARTCI, trancher l'hébergement.

## 7. Contribution collaborative : leçons du Nigeria (JRC / IITA / Banque mondiale)

- Projet *Food Price Crowdsourcing Africa* : plus de 700 volontaires invités, application mobile, contrôle qualité automatisé. [Nature, *Scientific Data*](https://www.nature.com/articles/s41597-023-02211-1)
- **Retenir est plus difficile que recruter** : sans rappels et micro-récompenses, les envois baissent. Environ **16 % de la foule** envoie des prix une semaine donnée. [PMC, *nudges*](https://pmc.ncbi.nlm.nih.gov/articles/PMC8886569/)
- **Motivation** : environ 93 % étaient intéressés par la donnée, environ 40 % par la récompense financière (4 € par envoi valide, jusqu'à 30 envois). [JRC](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC119273/fpca_a_quality_approach_to_real_time_prices_final_online.pdf)
- **Ce qui a marché** : des rappels par SMS appuyés sur la **norme sociale** (« d'autres contribuent ») ont augmenté la participation ; **montrer les prix** n'a pas suffi. **Freins cités** : manque de temps, récompense jugée faible, méfiance (« arnaque »).
- **Biais** : les relevés viennent surtout du détail (13 % de gros, 3 % de prix au producteur), avec des participants auto-sélectionnés, d'où une repondération par zone. Une comparaison de la Banque mondiale trouve une forte concordance avec des enquêtes classiques (corrélation 0,99 pour le maïs, 0,93 pour le riz). [Banque mondiale](https://blogs.worldbank.org/en/opendata/real-time-prices--real-results--comparing-crowdsourcing--ai--and)
- Incitation en crédit téléphonique : bien documentée pour des enquêtes (environ 0,25 USD de crédit par questionnaire en Rwanda), mais ⚠️ source de fournisseur. [Reloadly](https://www.reloadly.com/blog/afrisight-airtime-rewards/)

## 8. Vérification des comptes : coût réel

| Option | Prix constaté | Remarque |
|---|---|---|
| Agrégateurs locaux (SMSPro, Edoking, HSMS) | **9 à 20 FCFA par SMS** (HSMS : 2 500 FCFA les 150 SMS, soit environ 16,7 FCFA) | Connectés à Orange, MTN et Moov, avec API. [SMSPro](https://smspro.africa/cote-divoire) · [Edoking](https://www.edoking.com/cote-divoire.html) · [HSMS](https://hsms.ci/) |
| Passerelles internationales | **0,15 à 0,50 USD** par SMS (Plivo Orange 0,30 ; Twilio environ 0,49 ; Unimatrix 0,15) | De l'ordre de 10 fois plus cher que les agrégateurs locaux. [Plivo](https://www.plivo.com/sms/pricing/ci/) · [Twilio](https://www.twilio.com/en-us/sms/pricing/ci) |
| WhatsApp Business (authentification) | ⚠️ **Tarif Côte d'Ivoire introuvable** ; Meta révise ses tarifs chaque trimestre | À demander à un fournisseur agréé. |

Exemple : **1 000 inscriptions ≈ 13 000 à 20 000 FCFA** via un agrégateur local (≈ 20 à 30 €), contre environ 300 USD avec une passerelle internationale à 0,30 USD. Les grilles varient avec le volume et l'opérateur : demander un devis.

## 9. Stratégie affinée

1. **Positionnement** : « prix réels vérifiés, par commune, y compris marchés et boutiques », avec prix au kilo. À confirmer en testant Prixci (§3).
2. **Données** : (a) fiche supermarchés (60 prix) ; (b) relevés de marché pour 15 vivriers dans 2 à 3 communes ; (c) comparer à l'OCPV après accord de réutilisation.
3. **Contribution** : démarrer avec **10 à 20 relais de confiance** (récompense à tester) plutôt qu'une foule ouverte ; rappels par SMS ou WhatsApp avec preuve sociale (« 12 prix ajoutés cette semaine ») ; expliquer qui vous êtes pour éviter la méfiance.
4. **Identité** : code SMS via un agrégateur local, avec un module interchangeable (le code email actuel est un palier provisoire).
5. **Conformité** : avis d'un juriste, demande à l'ARTCI, décision sur l'hébergement, **avant** tout lancement public.
6. **Produit** : validité par catégorie (§5) ; unités de marché seulement après les entretiens.

### Indicateurs à suivre (6 semaines)

| Indicateur | Cible de départ | Pourquoi |
|---|---|---|
| Prix validés par semaine | 100+ | Volume |
| Couverture (produits × lieux avec un prix de moins de 14 jours) | 60 % de la liste | Utilité |
| Contributeurs actifs par semaine | 16 % ou plus des inscrits (repère Nigeria) | Santé de la communauté |
| Rétention à 4 semaines | À mesurer | Principal risque documenté |
| Coût par prix validé | À mesurer | Viabilité |
| Taux de rejet des relevés | Moins de 20 % | Qualité |
| Écart médian avec l'OCPV pour les produits communs | À mesurer | Crédibilité |

Les cibles sont des repères de départ, pas des chiffres établis : à corriger après 2 semaines.

### Guide d'entretien (15 à 20 personnes, 20 minutes)
1. Où avez-vous acheté vos produits de base la semaine dernière ? Combien de fois par semaine ?
2. Comment décidez-vous où acheter ? Comparez-vous les prix ? Comment ?
3. Quels produits vous inquiètent le plus côté prix ?
4. Avez-vous un smartphone ? Avez-vous un email ? Utilisez-vous WhatsApp tous les jours ?
5. Combien dépensez-vous en données par semaine ? Évitez-vous d'envoyer des photos ?
6. Connaissez-vous Prixci ou Promo CI ? L'avez-vous essayé ? Qu'en avez-vous pensé ?
7. Accepteriez-vous de noter un prix en magasin ? Dans quelles conditions ? Avec quelle récompense ?
8. Qu'est-ce qui vous ferait douter d'un prix affiché dans l'application ?
9. Quelles mesures utilisez-vous au marché (tas, bol, boîte…) ?
10. Quelle inquiétude auriez-vous à donner votre numéro de téléphone ?

## 10. Méthode et limites

- Recherche web à l'aide d'un moteur de recherche (avec résumés) : l'outil de lecture de pages était **indisponible** dans mon environnement, donc **aucun document primaire n'a été ouvert** (AFD, ARTCI, BCEAO, USDA, articles scientifiques). Je rapporte ce que les résumés en disent ; les chiffres clés sont à vérifier à la source avant publication.
- Beaucoup de sources sont secondaires (presse, cabinets, blogs) et de dates variées (2019 à 2026). Plusieurs chiffres se contredisent : je l'ai signalé là où c'est le cas.
- Les chiffres de WhatsApp, de smartphones et de mobile money sont des **estimations**.
- Rien sur le terrain : aucune de ces conclusions ne remplace les entretiens du §9.
- Pas de conseil juridique : le §6 sert à préparer la discussion avec un juriste.
