# Connecter un nom de domaine à ComparePrix (PythonAnywhere)

Préparé le 9 octobre 2026. **Je n'ai accès ni à votre bureau d'enregistrement, ni à votre compte PythonAnywhere, ni au DNS** (mon environnement ne résout aucun nom). Ce document est donc une procédure à suivre par vous, avec des outils du dépôt pour **vérifier chaque étape**. Les commandes utilisent déjà votre domaine, **compareprix.ci**.

## 0. Le domaine retenu : `compareprix.ci`

Le nom retenu est **compareprix.ci**, adresse officielle **`www.compareprix.ci`**. (Votre première indication, « comparepirx », avait les lettres « i » et « r » inversées : si vous avez aussi acheté cette variante, gardez-la seulement pour **rediriger** vers le bon nom, ce qui protège des fautes de frappe.)

Avant l'étape 1, **vérifiez que `compareprix.ci` est bien à vous** : l'outil WHOIS du registre [whois.nic.ci](https://whois.nic.ci) (indiqué par plusieurs bureaux d'enregistrement) dit s'il est enregistré et par qui. Je n'ai pas pu le vérifier : mon environnement ne résout aucun nom. S'il est libre, l'enregistrement passe par un **bureau d'enregistrement accrédité** (règle « premier arrivé, premier servi »). Les tarifs varient beaucoup (un bureau annonce 9 500 FCFA par an, un autre site évoque 25 000 à 50 000 FCFA : **comparez le prix TTC et ce qui est inclus**).

## 1. Ce que dit la documentation officielle

D'après les pages d'aide de PythonAnywhere, [Setting up a custom domain](https://help.pythonanywhere.com/pages/CustomDomains/) et [How to set up HTTPS](https://help.pythonanywhere.com/pages/HTTPSSetup) :
- Un **compte payant** est nécessaire pour utiliser votre propre domaine. Vérifiez l'offre et le tarif actuels sur la page des tarifs de PythonAnywhere.
- Le domaine est ajouté sur l'onglet **Web** (une entrée d'application web au nom du domaine).
- Il faut un enregistrement **CNAME** chez votre bureau d'enregistrement. Il ne peut **pas** se mettre sur le nom nu (`exemple.ci`) : il va sur **`www`** ou un sous-domaine.
- Le certificat HTTPS gratuit (**Let's Encrypt**, renouvellement automatique) s'active sur l'onglet Web, section **Security**, **après** que le DNS pointe vers PythonAnywhere.

⚠️ Je rapporte ces pages d'après un moteur de recherche, sans les avoir ouvertes. **Les intitulés exacts des boutons peuvent différer** : suivez la page d'aide à jour si l'écran ne correspond pas.

## 2. Les étapes, dans cet ordre exact

L'ordre protège le site existant : **il ne casse rien tant que l'étape 7 n'est pas faite**.

### Étape 1 : passer sur un compte payant PythonAnywhere
Si ce n'est pas fait. Notez : le **nombre d'applications web** autorisé dépend de l'offre. S'il n'y en a qu'une, l'application du domaine **remplace** l'ancienne (elle devra reprendre exactement sa configuration, voir étape 2).

### Étape 2 : ajouter le domaine sur l'onglet Web
Créez l'entrée d'application web pour `www.compareprix.ci` et **recopiez la configuration de l'ancienne** :
- dossier du code et dossier de travail (le dossier du projet) ;
- environnement virtuel (même version de Python) ;
- **contenu du fichier WSGI**, y compris toutes les variables `COMPAREPRIX_*` existantes : `COMPAREPRIX_ADMIN_TOKEN`, `COMPAREPRIX_SECRET_KEY` (**identique**, sinon les utilisateurs sont déconnectés), `COMPAREPRIX_DATA_DIR` (**même dossier**, sinon la base semble vide), `COMPAREPRIX_TRUSTED_PROXIES=1`.

Notez l'**adresse CNAME que PythonAnywhere affiche** pour cette application (de la forme `webapp-XXXXXXX.pythonanywhere.com`) : c'est la valeur à utiliser à l'étape 3. Ne l'inventez pas.

### Étape 3 : créer l'enregistrement DNS chez le bureau d'enregistrement
| Type | Nom (hôte) | Valeur |
|---|---|---|
| **CNAME** | `www` | l'adresse affichée par PythonAnywhere à l'étape 2 |

Pour le nom **sans www** (`compareprix.ci`) : le CNAME est impossible. Deux solutions : utiliser la **redirection web** (« URL forwarding ») du bureau d'enregistrement vers `https://www.compareprix.ci`, ou ne pas l'utiliser. Ne touchez pas aux enregistrements **MX** existants (courrier).

### Étape 4 : attendre la propagation et le vérifier
D'après des utilisateurs de PythonAnywhere, 10 à 60 minutes en général (parfois plus). Pour vérifier, depuis une console ou votre ordinateur :
```bash
python tools/check_domain.py www.compareprix.ci
```
À ce stade, **seul le contrôle DNS doit passer** ; le certificat échoue tant que l'étape 5 n'est pas faite : c'est normal.

### Étape 5 : activer le HTTPS
Onglet Web, section **Security**, ligne « HTTPS certificate » : choisir **Let's Encrypt auto-renew**. Puis activer la redirection HTTP vers HTTPS (« Force HTTPS ») en suivant la page d'aide. Relancez :
```bash
python tools/check_domain.py www.compareprix.ci --apex
```
Attendus : DNS OK, certificat OK, `http -> https` OK, `/healthz` OK, en-têtes OK. Le cookie sera marqué non sécurisé et HSTS absent : ce sont les étapes 6 et 7.

### Étape 6 : sécuriser les cookies
Dans le fichier WSGI de la **nouvelle** application, avant `from wsgi import application` :
```python
os.environ['COMPAREPRIX_COOKIE_SECURE'] = 'true'
```
Rechargez (**Reload**) et relancez `check_domain`. Le contrôle « cookie de session » doit passer.

> ⚠️ Tant que le HTTPS n'est pas confirmé (étape 5), **ne mettez pas** cette variable : les connexions échoueraient.

### Étape 7 : forcer une adresse unique (en dernier)
```python
os.environ['COMPAREPRIX_CANONICAL_HOST'] = 'www.compareprix.ci'
```
Toute visite sur l'ancienne adresse (`patrickeudess.pythonanywhere.com`) sera redirigée (301) vers le nouveau domaine, en gardant la page et les paramètres. `/healthz`, les écritures (POST) et l'accès local ne sont jamais redirigés. Vérifiez :
```bash
python tools/check_domain.py www.compareprix.ci --apex --alternate=patrickeudess.pythonanywhere.com
python tools/smoke_test.py https://www.compareprix.ci
```
Puis testez à la main, sur un **téléphone en données mobiles** : ouvrir le site, créer un compte, se déconnecter, se reconnecter.

> ⚠️ **Mettez cette variable en dernier.** Si elle est active avant que le nouveau nom fonctionne, l'ancienne adresse redirigerait vers un site inaccessible. **Pour annuler : supprimez la ligne et rechargez** (effet immédiat).

### Étape 8 (plus tard) : HSTS
```python
os.environ['COMPAREPRIX_HSTS'] = '1'
```
À activer **après une à deux semaines** de HTTPS stable. Le navigateur retient l'obligation de HTTPS pendant **un an** et applique `includeSubDomains` : si un autre sous-domaine du même domaine n'a pas de HTTPS, il deviendra inaccessible. **Cet effet ne s'annule pas côté navigateur.**

### Étape 9 : mettre à jour la redirection GitHub Pages
Les pages `index.html`, `panier.html`, etc. redirigent encore vers l'ancienne adresse.
```bash
python tools/set_site_url.py https://www.compareprix.ci            # simulation
python tools/set_site_url.py https://www.compareprix.ci --apply    # écrit
git diff && git commit -am "Pointer GitHub Pages vers le nouveau domaine" && git push
```

### Étape 10 : courrier électronique
Si vous envoyez des emails (code de vérification) avec une adresse du type `no-reply@compareprix.ci`, le fournisseur SMTP vous demandera d'**authentifier le domaine** en ajoutant chez le bureau d'enregistrement des enregistrements **TXT/CNAME (SPF, DKIM)** dont il vous donne les valeurs exactes. Sans cela, les messages arrivent en courrier indésirable ou sont refusés. Puis :
```python
os.environ['COMPAREPRIX_SMTP_FROM'] = 'ComparePrix <no-reply@compareprix.ci>'
```

### Étape 11 : mettre à jour les documents
Une fois `check_domain` **sans échec**, remplacez l'ancienne adresse dans les courriers non encore envoyés :
```bash
sed -i 's#https://patrickeudess.pythonanywhere.com#https://www.compareprix.ci#g' docs/COURRIERS.md
```
Puis vérifiez la politique de confidentialité (variable `COMPAREPRIX_CONTACT` : une adresse du type `contact@compareprix.ci` suppose une boîte aux lettres que vous devez créer) et la fiche de traitement ARTCI. **N'écrivez pas la nouvelle adresse dans un courrier avant qu'elle fonctionne** : un destinataire qui clique sur un lien mort perd confiance.

## 3. Si quelque chose ne va pas

| Symptôme | Cause probable | Que faire |
|---|---|---|
| `check_domain` : DNS ne résout pas | CNAME absent, mal écrit, ou pas encore propagé | Relire le nom et la valeur chez le bureau d'enregistrement ; attendre ; tester avec `nslookup www.compareprix.ci` |
| Avertissement de certificat dans le navigateur | Let's Encrypt pas activé ou activé avant la propagation du DNS | Réactiver l'option sur l'onglet Web une fois `check_domain` OK sur le DNS |
| Le site s'affiche mais « se déconnecte » sans arrêt | `COMPAREPRIX_COOKIE_SECURE=true` sans HTTPS fonctionnel, ou `COMPAREPRIX_SECRET_KEY` différente | Vérifier l'étape 5 ; recopier la même clé secrète |
| Le site paraît vide (aucun prix) | `COMPAREPRIX_DATA_DIR` ou chemin de la base différent sur la nouvelle application | Reprendre exactement les valeurs de l'ancienne |
| Boucle de redirection | Le domaine officiel indiqué ne correspond pas à l'adresse réellement servie | Supprimer `COMPAREPRIX_CANONICAL_HOST`, recharger, vérifier le nom |
| Les limites de connexions touchent tous les visiteurs | `COMPAREPRIX_TRUSTED_PROXIES=1` manquant | Le rajouter (cf. DEPLOIEMENT.md) |
| Les emails n'arrivent pas | Domaine non authentifié (SPF/DKIM) ou connexion SMTP sortante non autorisée par l'offre | Suivre l'étape 10 ; vérifier l'offre |

**Retour en arrière rapide** : retirer `COMPAREPRIX_CANONICAL_HOST`, recharger. L'ancienne adresse `patrickeudess.pythonanywhere.com` continue de fonctionner tant que son application web existe (sauf si votre offre n'autorise qu'une application).

## 4. Bonnes pratiques pour le domaine lui-même
- **Titulaire** : mettez le domaine au nom de la personne ou de la structure qui porte le projet, avec un email de contact que vous lisez.
- **Renouvellement** : activez le renouvellement automatique et notez la date d'expiration. Un domaine expiré se perd.
- **Sécurité du compte** chez le bureau d'enregistrement : mot de passe unique et vérification en deux étapes si elle est proposée.
- **Registre** : l'extension .ci est gérée par l'ARTCI (registre NIC.CI) ; l'enregistrement passe obligatoirement par un bureau d'enregistrement accrédité. [NIC.CI](https://www.nic.ci/index.php/le-point-ci/creer-votre-domaine).

## 5. Limites de ce document
- Je n'ai pu vérifier **ni la réservation du nom, ni ses enregistrements DNS, ni votre compte** : tout est à faire et à contrôler de votre côté.
- Les intitulés de l'interface PythonAnywhere viennent de pages d'aide lues via un moteur de recherche, pas d'un compte réel.
- Les prix des bureaux d'enregistrement et de PythonAnywhere ne sont pas vérifiés.
- Les outils (`check_domain.py`, `set_site_url.py`, la redirection) sont testés avec un réseau simulé : leur premier vrai essai sera le vôtre.
