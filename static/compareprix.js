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
const details=document.createElement('div'),title=document.createElement('h3');title.textContent=row.article;details.append(title);
const store=document.createElement('div');store.className='store';
const logo=logos[String(row.supermarche).trim().toLowerCase()];
if(logo){const image=document.createElement('img');image.src=logo;image.alt='';image.className='store-logo';image.loading='lazy';image.referrerPolicy='no-referrer';image.addEventListener('error',()=>image.remove());store.append(image);}
const name=document.createElement('span');name.textContent=row.supermarche;store.append(name);details.append(store);
const price=document.createElement('div');price.className='price';price.textContent=money.format(row.prix)+' FCFA';
const unit=document.createElement('span');unit.className='unit';unit.textContent='Format : '+(row.unite||'unité');price.append(unit);card.append(details,price);
const source=document.createElement('p');source.className='unit';source.textContent=row.date_releve?row.source+' · Relevé le '+row.date_releve+' · '+row.lieu:(row.source||'Prix de démonstration')+' · À confirmer';details.append(source);
if(Number.isFinite(row.prix_unitaire)){const normalized=document.createElement('span');normalized.className='unit';normalized.textContent=money.format(row.prix_unitaire)+' FCFA / '+row.unite_reference;price.append(normalized);}
try{const url=new URL(row.url);if(['https:','http:'].includes(url.protocol)&&!url.pathname.includes('example')){const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.className='product-link';link.textContent='Voir le produit';card.append(link);}}catch{}
content.append(card);
});
}
async function search(){
const term=input.value.trim();if(!term)return;
const sequence=++searchSequence;status.textContent='Recherche en cours…';section.hidden=true;
try{
const response=await fetch(document.body.dataset.prices || './data/articles.json');if(!response.ok)throw new Error();
const articles=await response.json();if(sequence!==searchSequence)return;
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

