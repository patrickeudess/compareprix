'use strict';
const logos = Object.freeze({
'carrefour':'https://carrefour.ci/wp-content/uploads/2023/08/carrefour-ci-logo.svg',
'cap sud':'https://groupeprosuma.com/wp-content/uploads/2022/10/logo-cap-sud-mini.png',
'casino':'https://groupeprosuma.com/wp-content/uploads/2020/12/logo-casno-supermarche-mini.png'
});
const form=document.getElementById('searchForm'),input=document.getElementById('searchInput'),filter=document.getElementById('storeFilter'),status=document.getElementById('status'),section=document.getElementById('resultsSection'),content=document.getElementById('resultsContent');
let results=[],searchSequence=0;
const money=new Intl.NumberFormat('fr-CI');
function render(){
const rows=results.filter(row=>!filter.value||row.supermarche===filter.value).sort((a,b)=>a.prix-b.prix);
document.getElementById('resultCount').textContent=rows.length+' offre'+(rows.length>1?'s':'')+' · Prix croissants';
content.replaceChildren();
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
const source=document.createElement('span');source.className='price-badge'+(row.date_releve?' dated':'');source.textContent=row.source==='prix_internet'?'🌐 Prix en ligne · consulté le '+row.date_consultation:row.statut==='donnee_exemple'||row.source==='exemple'?'Exemple':row.date_releve?'✓ Validé · '+row.date_releve:'◷ À confirmer';identity.append(source);const stock=document.createElement('p');stock.className='stock-badge '+(row.disponibilite==='available'?'available':row.disponibilite==='out_of_stock'?'out-of-stock':'unknown');stock.textContent=({available:'🟢 Disponible',out_of_stock:'🔴 Rupture de stock'})[row.disponibilite]||'⚪ Disponibilité inconnue';if(row.date_disponibilite)stock.textContent+=' · '+row.date_disponibilite;identity.append(stock);
if(row.lieu){const place=document.createElement('p');place.className='offer-place';place.textContent='📍 '+row.lieu;identity.append(place);} 
if(Number.isFinite(row.prix_unitaire)){const normalized=document.createElement('span');normalized.className='unit';normalized.textContent=money.format(row.prix_unitaire)+' FCFA / '+row.unite_reference;price.append(normalized);}
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
const response=await fetch(document.body.dataset.prices || './data/articles.json');if(!response.ok)throw new Error();
const articles=await response.json();syncBasketAvailability(articles);if(sequence!==searchSequence)return;
results=articles.filter(row=>String(row.article||'').toLocaleLowerCase('fr').includes(term.toLocaleLowerCase('fr'))&&Number.isFinite(row.prix)&&row.prix>0);
filter.replaceChildren(new Option('Tous les magasins',''));
[...new Set(results.map(row=>row.supermarche))].sort((a,b)=>a.localeCompare(b,'fr')).forEach(name=>filter.append(new Option(name,name)));
status.textContent=results.length?'':'Aucun prix trouvé pour « '+term+' ». Essayez un autre nom de produit.';
section.hidden=!results.length;render();
}catch{if(sequence===searchSequence)status.textContent='Impossible de charger les prix. Réessayez dans un instant.';}
}
form.addEventListener('submit',event=>{event.preventDefault();search();});
document.querySelectorAll('[data-search]').forEach(button=>button.addEventListener('click',()=>{input.value=button.dataset.search;search();}));
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