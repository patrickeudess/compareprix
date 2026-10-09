'use strict';
const logos = Object.freeze({
'carrefour':'https://carrefour.ci/wp-content/uploads/2023/08/carrefour-ci-logo.svg',
'cap sud':'https://groupeprosuma.com/wp-content/uploads/2022/10/logo-cap-sud-mini.png',
'casino':'https://groupeprosuma.com/wp-content/uploads/2020/12/logo-casno-supermarche-mini.png'
});
const form=document.getElementById('searchForm'),input=document.getElementById('searchInput'),filter=document.getElementById('storeFilter'),status=document.getElementById('status'),section=document.getElementById('resultsSection'),content=document.getElementById('resultsContent');
let results=[],searchSequence=0,cataloguePromise,searchTimer,catalogueReady=false;
function normalizeSearch(value){return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('fr').replace(/[^a-z0-9]+/g,' ').trim();}
const searchAliases={pate:'spaghetti',pates:'spaghetti',tomates:'tomate',sardine:'sardines',cafe:'cafe',nescafe:'cafe',the:'the'};
function matchesProduct(row,term){
const haystack=normalizeSearch([row.article,row.marque,row.brand,row.unite].filter(Boolean).join(' '));
return normalizeSearch(term).split(' ').filter(Boolean).every(word=>haystack.includes(word)||haystack.includes(searchAliases[word]||word));
}
async function loadCatalogue(){
if(!cataloguePromise)cataloguePromise=fetch(document.body.dataset.prices||'./data/articles.json').then(response=>{if(!response.ok)throw new Error();return response.json();}).then(articles=>{
if(!Array.isArray(articles))throw new Error();syncBasketAvailability(articles);
const names=[...new Set(articles.map(row=>row.article).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'fr'));
const list=document.getElementById('productSuggestions');if(list)list.replaceChildren(...names.map(name=>new Option(name,name)));
return articles;
}).catch(error=>{cataloguePromise=null;throw error;});
return cataloguePromise;
}

const cityFilter=document.createElement('select'),communeFilter=document.createElement('select'),channelFilter=document.createElement('select'),orderFilter=document.createElement('select');
cityFilter.id='cityFilter';communeFilter.id='communeFilter';channelFilter.id='channelFilter';orderFilter.id='orderFilter';
const geo=document.createElement('div');geo.className='search-filters';geo.setAttribute('aria-label','Affiner la comparaison');
[['Ville',cityFilter],['Commune',communeFilter],['Type d’offre',channelFilter]].forEach(([text,select])=>{const label=document.createElement('label');label.htmlFor=select.id;label.className='search-filter';const caption=document.createElement('span');caption.className='filter-caption';caption.textContent=({cityFilter:'📍 ',communeFilter:'🏘️ ',channelFilter:'🏪 ',orderFilter:'↕ '})[select.id]+text;label.append(caption);label.append(select);geo.append(label);});
cityFilter.append(new Option('Toutes les villes',''));communeFilter.append(new Option('Toutes les communes',''));
[['Tous',''],['En magasin','store'],['En ligne','online']].forEach(([text,value])=>channelFilter.append(new Option(text,value)));
[['Prix du format','price'],['Prix par kg / litre','unit']].forEach(([text,value])=>orderFilter.append(new Option(text,value)));
const filtersBox=document.createElement('details');filtersBox.className='filters-box';const filtersSummary=document.createElement('summary');const filtersLabel=document.createElement('span');filtersLabel.textContent='Filtres : ville, commune, type d’offre';const filtersBadge=document.createElement('b');filtersBadge.className='filters-count';filtersBadge.hidden=true;filtersSummary.append(filtersLabel,filtersBadge);filtersBox.append(filtersSummary,geo);form.after(filtersBox);function updateFiltersBadge(){const active=[cityFilter,communeFilter,channelFilter].filter(select=>select.value).length;filtersBadge.hidden=!active;filtersBadge.textContent=active+(active>1?' actifs':' actif');if(active)filtersBox.open=true;}
const comparisonHint=document.createElement('p');comparisonHint.className='hint';comparisonHint.textContent='Comparez la même marque et le même format. En ligne : livraison et frais à confirmer auprès du vendeur.';geo.after(comparisonHint);
let geoCities=[],geoCommunes={};
fetch('./static/locations.json').then(r=>r.json()).then(data=>{geoCities=data.cities||[];geoCommunes=data.communesByCity||{};syncCities();syncCommunes();}).catch(()=>{});
function onlineOffer(row){return row.source==='prix_internet'||row.type_offre==='online';}
function commune(row){return row.commune||row.quartier||'';}
function syncCities(){const selected=cityFilter.value;cityFilter.replaceChildren(new Option('Toutes les villes',''));[...new Set([...geoCities,...results.map(r=>r.ville).filter(Boolean)])].sort((a,b)=>a.localeCompare(b,'fr')).forEach(name=>cityFilter.append(new Option(name,name)));cityFilter.value=selected;}
function syncCommunes(){const selected=communeFilter.value;communeFilter.replaceChildren(new Option('Toutes les communes',''));[...new Set([...(geoCommunes[cityFilter.value]||[]),...results.filter(r=>!cityFilter.value||r.ville===cityFilter.value).map(commune).filter(Boolean)])].sort((a,b)=>a.localeCompare(b,'fr')).forEach(name=>communeFilter.append(new Option(name,name)));communeFilter.value=[...communeFilter.options].some(o=>o.value===selected)?selected:'';}
[communeFilter,channelFilter,orderFilter].forEach(select=>select.addEventListener('change',render));
cityFilter.addEventListener('change',()=>{communeFilter.value='';syncCommunes();render();});

const money=new Intl.NumberFormat('fr-CI');
function shortDate(value){const date=new Date(String(value)+'T12:00:00');return Number.isNaN(date.getTime())?String(value):date.toLocaleDateString('fr-FR',{day:'numeric',month:'short'});}
// Repère national sous le prix : texte neutre, source cliquable. Le ton d'alerte n'est utilisé que si le verdict est établi (produit, format et zone concordent).
function referenceNote(row,parent){
const ref=row.reference;if(!ref)return;
const note=document.createElement('p');note.className='ref-note'+(ref.position==='above'?' above':'');
const fullDate=value=>{const date=new Date(String(value)+'T12:00:00');return Number.isNaN(date.getTime())?String(value):date.toLocaleDateString('fr-FR',{day:'numeric',month:'long',year:'numeric'});};
const period=ref.valid_to?' jusqu’au '+fullDate(ref.valid_to):' depuis le '+fullDate(ref.valid_from);
const where=ref.zone?' ('+ref.zone+')':'';
if(ref.kind==='plafond'){note.textContent='Plafond indiqué'+where+' : '+money.format(ref.value)+' FCFA'+period+'.';
if(ref.position==='above')note.textContent+=' Ce prix est supérieur au plafond indiqué : vérifiez l’étiquette.';}
else{const gap=Number.isFinite(ref.ecart_pct)?' · cet article : '+(ref.ecart_pct>0?'+':'')+ref.ecart_pct+' %':'';note.textContent='Moyenne observée'+where+' : '+money.format(ref.value)+' FCFA / '+ref.unit_base+period+gap+'.';}
note.append(' ');
try{const url=new URL(ref.source_url);if(url.protocol==='https:'||url.protocol==='http:'){const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent='Source : '+ref.source_name;note.append(link);}else throw 0;}catch{note.append('Source : '+ref.source_name);}
parent.append(note);
}
const sortSeg=document.createElement('div');sortSeg.className='sort-seg';sortSeg.setAttribute('role','group');sortSeg.setAttribute('aria-label','Trier les offres');sortSeg.hidden=true;
[['Moins cher','price'],['Prix par kg / litre','unit']].forEach(([text,value])=>{const button=document.createElement('button');button.type='button';button.textContent=text;button.dataset.value=value;button.addEventListener('click',()=>{orderFilter.value=value;render();});sortSeg.append(button);});
content.before(sortSeg);
function showSkeleton(){section.hidden=false;sortSeg.hidden=true;document.getElementById('resultCount').textContent='Chargement des prix…';content.replaceChildren(...[0,1,2].map(()=>{const placeholder=document.createElement('div');placeholder.className='offer skeleton';placeholder.setAttribute('aria-hidden','true');return placeholder;}));}
function render(){
const rows=results.filter(row=>(!filter.value||row.supermarche===filter.value)&&(!cityFilter.value||row.ville===cityFilter.value||(onlineOffer(row)&&(row.zones_livraison||[]).includes(cityFilter.value)))&&(!communeFilter.value||commune(row)===communeFilter.value)&&(!channelFilter.value||(channelFilter.value==='online')===onlineOffer(row))).sort((a,b)=>orderFilter.value==='unit'?(a.prix_unitaire??Infinity)-(b.prix_unitaire??Infinity):a.prix-b.prix);
document.getElementById('resultCount').textContent=rows.length+' offre'+(rows.length>1?'s':'')+(orderFilter.value==='unit'?' · Prix par kg / litre':' · Prix croissants');
content.replaceChildren();sortSeg.hidden=false;sortSeg.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.value===orderFilter.value)));updateFiltersBadge();
if(!rows.length){const empty=document.createElement('p');empty.textContent='Aucune offre pour ces filtres. Essayez une autre ville ou ajoutez un prix près de chez vous.';content.append(empty);}
const unitOf=row=>row.unite_reference||row.unite_base||'unité';
const groupKey=row=>String(row.article).toLocaleLowerCase('fr')+'|'+unitOf(row);
const groups=new Map();rows.forEach(row=>{if(!Number.isFinite(row.prix_unitaire))return;const key=groupKey(row),group=groups.get(key)||{count:0,best:Infinity};group.count++;group.best=Math.min(group.best,row.prix_unitaire);groups.set(key,group);});
rows.forEach((row,index)=>{
const card=document.createElement('article');card.className='offer';card.style.setProperty('--i',Math.min(index,10));
const group=groups.get(groupKey(row));const isBest=Boolean(group&&group.count>1&&row.prix_unitaire===group.best);if(isBest)card.classList.add('is-best');
const details=document.createElement('div');details.className='offer-details';
const visual=document.createElement('div');visual.className='product-visual';visual.setAttribute('aria-hidden','true');
const product=String(row.article).toLocaleLowerCase('fr');visual.textContent=product.includes('riz')?'🌾':product.includes('huile')?'🫒':product.includes('lait')?'🥛':product.includes('pain')?'🥖':product.includes('sucre')?'🧊':product.includes('café')||product.includes('cafe')?'☕':product.includes('eau')?'💧':'🛍️';
const identity=document.createElement('div'),title=document.createElement('h3');title.textContent=row.article;if(isBest){const flag=document.createElement('p');flag.className='best-flag';flag.textContent='Meilleur prix '+(({kg:'au kilo',L:'au litre',l:'au litre'})[unitOf(row)]||'par '+unitOf(row));identity.append(flag);}identity.append(title);details.append(visual,identity);
const store=document.createElement('div');store.className='store';
const logo=logos[String(row.supermarche).trim().toLowerCase()];
if(logo){const image=document.createElement('img');image.src=logo;image.alt='';image.className='store-logo';image.loading='lazy';image.referrerPolicy='no-referrer';image.addEventListener('error',()=>image.remove());store.append(image);}
const name=document.createElement('span');name.textContent=row.supermarche;store.append(name);identity.append(store);
const price=document.createElement('div');price.className='price';price.textContent=money.format(row.prix)+' FCFA';
const unit=document.createElement('span');unit.className='unit';unit.textContent='Format : '+(row.unite||'unité');price.append(unit);card.append(details,price);
const more=document.createElement('details');more.className='offer-more';const moreSummary=document.createElement('summary');moreSummary.textContent='Détails et actions';more.append(moreSummary);
const source=document.createElement('span');source.className='price-badge'+(row.date_releve?' dated':'');source.textContent=row.source==='prix_internet'?'🌐 Prix en ligne · vu le '+shortDate(row.date_consultation):row.statut==='donnee_exemple'||row.source==='exemple'?'Exemple':row.date_releve?'✓ Validé · '+row.date_releve:'◷ À confirmer';if(row.source==='prix_internet'&&row.actualisation!=='ok')source.textContent+=' · '+(row.actualisation==='unavailable'?'Actualisation indisponible': 'Vérification en cours');identity.append(source);referenceNote(row,identity);const stock=document.createElement('p');stock.className='stock-badge '+(row.disponibilite==='available'?'available':row.disponibilite==='out_of_stock'?'out-of-stock':'unknown');stock.textContent=({available:'🟢 Disponible',out_of_stock:'🔴 Rupture de stock'})[row.disponibilite]||'⚪ Disponibilité inconnue';if(row.date_disponibilite)stock.textContent+=' · '+row.date_disponibilite;more.append(stock);
const locationInfo=document.createElement('p');locationInfo.className='offer-place';locationInfo.textContent=onlineOffer(row)?'🚚 '+((row.zones_livraison||[]).length?'Livraison : '+row.zones_livraison.join(', '):'Zone de livraison à confirmer')+' · Frais à confirmer':'📍 '+[row.ville,commune(row),row.boutique].filter(Boolean).join(' · ');more.append(locationInfo);
if(!onlineOffer(row)&&row.ville&&commune(row)&&row.boutique){const map=document.createElement('a');map.href='https://www.google.com/maps/search/?api=1&query='+encodeURIComponent([row.boutique,commune(row),row.ville,'Côte d’Ivoire'].join(', '));map.target='_blank';map.rel='noopener noreferrer';map.textContent='📍 Rechercher sur la carte';more.append(map);}
if(row.lieu){const place=document.createElement('p');place.className='offer-place';place.textContent='📍 '+row.lieu;more.append(place);} 
if(Number.isFinite(row.prix_unitaire)){const normalized=document.createElement('span');normalized.className='unit';normalized.textContent=money.format(row.prix_unitaire)+' FCFA / '+unitOf(row);price.append(normalized);}
const links=document.createElement('div');links.className='offer-links';
if(row.source_catalogue){try{const sourceUrl=new URL(row.source_catalogue);if(sourceUrl.protocol==='https:'){const sourceLink=document.createElement('a');sourceLink.href=sourceUrl.href;sourceLink.target='_blank';sourceLink.rel='noopener noreferrer';sourceLink.className='source-link';sourceLink.textContent='Voir la source du prix';links.append(sourceLink);}}catch{}}
try{const url=new URL(row.url);if(['https:','http:'].includes(url.protocol)&&!url.pathname.includes('example')){const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.className='product-link';link.textContent='Voir le produit';links.append(link);}}catch{}if(links.children.length)card.append(links);
const actions=document.createElement('div');actions.className='offer-actions';
const add=document.createElement('button');add.type='button';add.className='basket-add';add.textContent='＋ Ajouter';add.addEventListener('click',()=>{addToBasket(row);add.textContent='✓ Ajouté';add.classList.add('added');if(navigator.vibrate)navigator.vibrate(15);clearTimeout(add.resetTimer);add.resetTimer=setTimeout(()=>{add.textContent='＋ Ajouter';add.classList.remove('added');},1600);});if(row.disponibilite==='out_of_stock'){add.disabled=true;add.textContent='Indisponible';}actions.append(add);
const share=document.createElement('a');share.className='share-link';share.target='_blank';share.rel='noopener noreferrer';share.href='https://wa.me/?text='+encodeURIComponent(row.article+' : '+money.format(row.prix)+' FCFA chez '+row.supermarche+(isBest?' (meilleur prix)':'')+' — comparé sur ComparePrix '+location.href.split('#')[0]);share.textContent='Partager';share.setAttribute('aria-label','Partager '+row.article+' sur WhatsApp');actions.append(share);
const report=document.createElement('button');report.type='button';report.textContent='⚑ Signaler';report.setAttribute('aria-label','Signaler une erreur sur '+row.article);report.addEventListener('click',()=>openReport(row));more.append(report);
const update=document.createElement('a');const target=new URL('./compte.html',location.href);target.searchParams.set('article',row.article);target.searchParams.set('store',row.supermarche);target.searchParams.set('format',row.unite||'');target.searchParams.set('location',row.lieu||'');target.searchParams.set('city',row.ville||'');target.searchParams.set('district',row.quartier||'');target.searchParams.set('shop',row.boutique||'');target.searchParams.set('intent','update');target.hash='account';update.href=target.href;update.textContent='↻ Actualiser';update.setAttribute('aria-label','Partager un prix actualisé pour '+row.article);more.append(update);card.append(actions,more);
content.append(card);
});
}
async function search(){
const term=input.value.trim();
const sequence=++searchSequence;status.textContent='Recherche en cours…';if(!catalogueReady)showSkeleton();
try{
const articles=await loadCatalogue();catalogueReady=true;if(sequence!==searchSequence)return;
results=articles.filter(row=>matchesProduct(row,term)&&Number.isFinite(row.prix)&&row.prix>0);
const selectedStore=filter.value;filter.replaceChildren(new Option('Tous les magasins',''));
[...new Set(results.map(row=>row.supermarche))].sort((a,b)=>a.localeCompare(b,'fr')).forEach(name=>filter.append(new Option(name,name)));
if([...filter.options].some(option=>option.value===selectedStore))filter.value=selectedStore;
syncCities();syncCommunes();
status.textContent=results.length?'':'Aucun prix trouvé pour « '+term+' ». Essayez un autre nom de produit.';
section.hidden=!results.length;render();document.body.classList.toggle('searched',Boolean(term)&&results.length>0);
}catch{if(sequence===searchSequence){section.hidden=true;status.textContent='Impossible de charger les prix. Réessayez dans un instant.';}}
}
form.addEventListener('submit',event=>{event.preventDefault();clearTimeout(searchTimer);search();});
input.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(search,180);});
document.getElementById('showAllProducts')?.addEventListener('click',()=>{clearTimeout(searchTimer);input.value='';filter.value='';search();input.focus();});
document.querySelectorAll('[data-search]').forEach(button=>button.addEventListener('click',()=>{clearTimeout(searchTimer);input.value=button.dataset.search;filter.value='';search();}));
filter.addEventListener('change',render);


function openReport(row){
const dialog=document.createElement('dialog');dialog.className='report-dialog';
const heading=document.createElement('h2');heading.textContent='Signaler une erreur';
const context=document.createElement('p');context.textContent=row.article+' · '+row.supermarche;
const message=document.createElement('p');message.setAttribute('role','status');message.setAttribute('aria-live','polite');
const reportForm=document.createElement('form');
const label=document.createElement('label');label.textContent='Quelle erreur avez-vous constatée ?';
const reason=document.createElement('select');[['wrong_price','Prix incorrect'],['unavailable','Produit indisponible'],['wrong_format','Format incorrect'],['other','Autre erreur']].forEach(([value,text])=>reason.append(new Option(text,value)));label.append(reason);
const commentLabel=document.createElement('label');commentLabel.textContent='Précisions (facultatives)';
const comment=document.createElement('textarea');comment.maxLength=2000;commentLabel.append(comment);
const send=document.createElement('button');send.type='submit';send.textContent='Envoyer le signalement';
const close=document.createElement('button');close.type='button';close.textContent='Fermer';close.addEventListener('click',()=>dialog.close());
reportForm.append(label,commentLabel,send);dialog.append(heading,context,reportForm,message,close);document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove());dialog.showModal();
if(!document.body.dataset.prices){message.textContent='L’envoi des signalements n’est pas encore disponible sur cette version en ligne.';send.disabled=true;return;}
let sessionToken='';
send.disabled=true;
fetch('/api/session').then(response=>{if(!response.ok)throw new Error();return response.json();}).then(data=>{
if(!dialog.isConnected)return;
sessionToken=data.csrf;
if(data.user){send.disabled=false;}else{message.textContent='Connectez-vous pour envoyer un signalement. La consultation des prix reste libre.';const login=document.createElement('a');login.href='./compte.html';login.textContent='Se connecter ou créer un compte';dialog.append(login);}
}).catch(()=>message.textContent='Connexion au serveur impossible. Réessayez plus tard.');
reportForm.addEventListener('submit',async event=>{
event.preventDefault();send.disabled=true;
try{const response=await fetch('/api/reports',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':sessionToken},body:JSON.stringify({article:row.article,store:row.supermarche,reason:reason.value,comment:comment.value})});const data=await response.json();message.textContent=data.message;if(response.ok){reportForm.hidden=true;}else send.disabled=false;}catch{message.textContent='Envoi impossible. Réessayez.';send.disabled=false;}
});
}



search();