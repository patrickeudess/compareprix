'use strict';
const logos = Object.freeze({
'carrefour':'https://carrefour.ci/wp-content/uploads/2023/08/carrefour-ci-logo.svg',
'cap sud':'https://groupeprosuma.com/wp-content/uploads/2022/10/logo-cap-sud-mini.png',
'casino':'https://groupeprosuma.com/wp-content/uploads/2020/12/logo-casno-supermarche-mini.png'
});
const form=document.getElementById('searchForm'),input=document.getElementById('searchInput'),filter=document.getElementById('storeFilter'),status=document.getElementById('status'),section=document.getElementById('resultsSection'),content=document.getElementById('resultsContent');
let results=[],searchSequence=0,cataloguePromise,searchTimer;
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
const geo=document.createElement('div');geo.className='grid';geo.style.cssText='display:flex;flex-wrap:wrap;gap:12px;margin:16px 0';
[['Ville',cityFilter],['Commune',communeFilter],['Type d’offre',channelFilter],['Comparer par',orderFilter]].forEach(([text,select])=>{const label=document.createElement('label');label.htmlFor=select.id;label.textContent=text;select.style.cssText='display:block;max-width:100%;padding:10px;border-radius:10px';label.append(select);geo.append(label);});
cityFilter.append(new Option('Toutes les villes',''));communeFilter.append(new Option('Toutes les communes',''));
[['Tous',''],['En magasin','store'],['En ligne','online']].forEach(([text,value])=>channelFilter.append(new Option(text,value)));
[['Prix du format','price'],['Prix par kg / litre','unit']].forEach(([text,value])=>orderFilter.append(new Option(text,value)));
form.after(geo);
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
function render(){
const rows=results.filter(row=>(!filter.value||row.supermarche===filter.value)&&(!cityFilter.value||row.ville===cityFilter.value||(onlineOffer(row)&&(row.zones_livraison||[]).includes(cityFilter.value)))&&(!communeFilter.value||commune(row)===communeFilter.value)&&(!channelFilter.value||(channelFilter.value==='online')===onlineOffer(row))).sort((a,b)=>orderFilter.value==='unit'?(a.prix_unitaire??Infinity)-(b.prix_unitaire??Infinity):a.prix-b.prix);
document.getElementById('resultCount').textContent=rows.length+' offre'+(rows.length>1?'s':'')+(orderFilter.value==='unit'?' · Prix par kg / litre':' · Prix croissants');
content.replaceChildren();
if(!rows.length){const empty=document.createElement('p');empty.textContent='Aucune offre pour ces filtres. Essayez une autre ville ou ajoutez un prix près de chez vous.';content.append(empty);}
rows.forEach(row=>{
const card=document.createElement('article');card.className='offer';
const details=document.createElement('div');details.className='offer-details';
const visual=document.createElement('div');visual.className='product-visual';visual.setAttribute('aria-hidden','true');
const product=String(row.article).toLocaleLowerCase('fr');visual.textContent=product.includes('riz')?'🌾':product.includes('huile')?'🫒':product.includes('lait')?'🥛':product.includes('pain')?'🥖':product.includes('sucre')?'🧊':product.includes('café')||product.includes('cafe')?'☕':product.includes('eau')?'💧':'🛍️';
const identity=document.createElement('div'),title=document.createElement('h3');title.textContent=row.article;identity.append(title);details.append(visual,identity);
const store=document.createElement('div');store.className='store';
const logo=logos[String(row.supermarche).trim().toLowerCase()];
if(logo){const image=document.createElement('img');image.src=logo;image.alt='';image.className='store-logo';image.loading='lazy';image.referrerPolicy='no-referrer';image.addEventListener('error',()=>image.remove());store.append(image);}
const name=document.createElement('span');name.textContent=row.supermarche;store.append(name);identity.append(store);
const price=document.createElement('div');price.className='price';price.textContent=money.format(row.prix)+' FCFA';
const unit=document.createElement('span');unit.className='unit';unit.textContent='Format : '+(row.unite||'unité');price.append(unit);card.append(details,price);
const source=document.createElement('span');source.className='price-badge'+(row.date_releve?' dated':'');source.textContent=row.source==='prix_internet'?'🌐 Prix en ligne · consulté le '+row.date_consultation:row.statut==='donnee_exemple'||row.source==='exemple'?'Exemple':row.date_releve?'✓ Validé · '+row.date_releve:'◷ À confirmer';if(row.source==='prix_internet'&&row.actualisation!=='ok')source.textContent+=' · '+(row.actualisation==='unavailable'?'Actualisation indisponible': 'Vérification en cours');identity.append(source);const stock=document.createElement('p');stock.className='stock-badge '+(row.disponibilite==='available'?'available':row.disponibilite==='out_of_stock'?'out-of-stock':'unknown');stock.textContent=({available:'🟢 Disponible',out_of_stock:'🔴 Rupture de stock'})[row.disponibilite]||'⚪ Disponibilité inconnue';if(row.date_disponibilite)stock.textContent+=' · '+row.date_disponibilite;identity.append(stock);
const locationInfo=document.createElement('p');locationInfo.className='offer-place';locationInfo.textContent=onlineOffer(row)?'🚚 '+((row.zones_livraison||[]).length?'Livraison : '+row.zones_livraison.join(', '):'Zone de livraison à confirmer')+' · Frais à confirmer':'📍 '+[row.ville,commune(row),row.boutique].filter(Boolean).join(' · ');identity.append(locationInfo);
if(!onlineOffer(row)&&row.ville&&commune(row)&&row.boutique){const map=document.createElement('a');map.href='https://www.google.com/maps/search/?api=1&query='+encodeURIComponent([row.boutique,commune(row),row.ville,'Côte d’Ivoire'].join(', '));map.target='_blank';map.rel='noopener noreferrer';map.textContent='📍 Rechercher sur la carte';identity.append(map);}
if(row.lieu){const place=document.createElement('p');place.className='offer-place';place.textContent='📍 '+row.lieu;identity.append(place);} 
if(Number.isFinite(row.prix_unitaire)){const normalized=document.createElement('span');normalized.className='unit';normalized.textContent=money.format(row.prix_unitaire)+' FCFA / '+row.unite_reference;price.append(normalized);}
if(row.source_catalogue){try{const sourceUrl=new URL(row.source_catalogue);if(sourceUrl.protocol==='https:'){const sourceLink=document.createElement('a');sourceLink.href=sourceUrl.href;sourceLink.target='_blank';sourceLink.rel='noopener noreferrer';sourceLink.textContent='Consulter la source du prix';card.append(sourceLink);}}catch{}}
try{const url=new URL(row.url);if(['https:','http:'].includes(url.protocol)&&!url.pathname.includes('example')){const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.className='product-link';link.textContent='Voir le produit';card.append(link);}}catch{}
const actions=document.createElement('div');actions.className='offer-actions';
const add=document.createElement('button');add.type='button';add.className='basket-add';add.textContent='＋ Ajouter';add.addEventListener('click',()=>{addToBasket(row);add.textContent='✓ Ajouté';});if(row.disponibilite==='out_of_stock'){add.disabled=true;add.textContent='Indisponible';}actions.append(add);
const report=document.createElement('button');report.type='button';report.textContent='⚑ Signaler';report.setAttribute('aria-label','Signaler une erreur sur '+row.article);report.addEventListener('click',()=>openReport(row));actions.append(report);
const update=document.createElement('a');const target=new URL('./compte.html',location.href);target.searchParams.set('article',row.article);target.searchParams.set('store',row.supermarche);target.searchParams.set('format',row.unite||'');target.searchParams.set('location',row.lieu||'');target.searchParams.set('city',row.ville||'');target.searchParams.set('district',row.quartier||'');target.searchParams.set('shop',row.boutique||'');target.searchParams.set('intent','update');target.hash='account';update.href=target.href;update.textContent='↻ Actualiser';update.setAttribute('aria-label','Partager un prix actualisé pour '+row.article);actions.append(update);card.append(actions);
content.append(card);
});
}
async function search(){
const term=input.value.trim();
const sequence=++searchSequence;status.textContent='Recherche en cours…';section.hidden=true;
try{
const articles=await loadCatalogue();if(sequence!==searchSequence)return;
results=articles.filter(row=>matchesProduct(row,term)&&Number.isFinite(row.prix)&&row.prix>0);
const selectedStore=filter.value;filter.replaceChildren(new Option('Tous les magasins',''));
[...new Set(results.map(row=>row.supermarche))].sort((a,b)=>a.localeCompare(b,'fr')).forEach(name=>filter.append(new Option(name,name)));
if([...filter.options].some(option=>option.value===selectedStore))filter.value=selectedStore;
syncCities();syncCommunes();
status.textContent=results.length?'':'Aucun prix trouvé pour « '+term+' ». Essayez un autre nom de produit.';
section.hidden=!results.length;render();
}catch{if(sequence===searchSequence)status.textContent='Impossible de charger les prix. Réessayez dans un instant.';}
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