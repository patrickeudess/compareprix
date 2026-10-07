'use strict';
const basketKey='compareprix-basket-v1',basketMoney=new Intl.NumberFormat('fr-CI');
let basket=[],basketToastTimer;
try{const saved=JSON.parse(localStorage.getItem(basketKey)||'[]');if(Array.isArray(saved))basket=saved.filter(item=>item&&typeof item.id==='string'&&typeof item.article==='string'&&typeof item.store==='string'&&typeof item.format==='string'&&Number.isSafeInteger(item.price)&&item.price>0&&item.price<=100000000&&Number.isInteger(item.quantity)&&item.quantity>=1&&item.quantity<=99).slice(0,100);}catch{}
const basketList=document.getElementById('basketItems'),basketNotice=document.getElementById('basketNotice')||document.createElement('p');
function persistBasket(){try{localStorage.setItem(basketKey,JSON.stringify(basket));}catch{basketNotice.textContent='Le panier reste disponible ici, mais ne peut pas être conservé sur cet appareil.';}}
function addToBasket(row){
if(row.disponibilite==='out_of_stock')return;
const item={article:String(row.article||'').slice(0,200),store:String(row.supermarche||'').slice(0,120),format:String(row.unite||'unité').slice(0,100),place:String(row.lieu||'').slice(0,200),date:String(row.date_releve||''),availability:row.disponibilite||'unknown',availabilityDate:row.date_disponibilite||'',price:row.prix,quantity:1};
if(!Number.isSafeInteger(item.price)||item.price<=0||item.price>100000000)return;
item.id=JSON.stringify([item.article,item.store,item.format,item.place,item.price]);
const existing=basket.find(entry=>entry.id===item.id);
if(existing){if(existing.quantity>=99){basketNotice.textContent='La quantité maximale est de 99 pour cet article.';return;}existing.quantity++;}
else{if(basket.length>=100){basketNotice.textContent='Le panier peut contenir jusqu’à 100 offres différentes.';return;}basket.push(item);}
basketNotice.textContent=item.article+' ajouté au panier.';const toast=document.getElementById('basketToast');if(toast){toast.textContent='✓ '+item.article+' ajouté';clearTimeout(basketToastTimer);basketToastTimer=setTimeout(()=>toast.textContent='',2600);}persistBasket();renderBasket();
}
function renderBasket(){
if(!basketList){renderBasketTotals();return;}basketList.replaceChildren();let total=0,count=0;
const stores=new Map();
for(const item of basket){
const subtotal=item.price*item.quantity;total+=subtotal;count+=item.quantity;stores.set(item.store,(stores.get(item.store)||0)+subtotal);
const line=document.createElement('article');line.className='basket-line';
const details=document.createElement('div'),title=document.createElement('h3');title.textContent=item.article;
const description=document.createElement('p');description.textContent=[item.store,item.format,item.place].filter(Boolean).join(' · ');
const price=document.createElement('p');price.className='unit';price.textContent=basketMoney.format(item.price)+' FCFA par format'+(item.date?' · Relevé le '+item.date:' · Prix à confirmer');details.append(title,description,price);const stock=document.createElement('p');stock.className='stock-badge';stock.textContent=({available:'🟢 Disponible',out_of_stock:'🔴 Rupture signalée : choisissez une autre offre'})[item.availability]||'⚪ Disponibilité inconnue';if(item.availabilityDate)stock.textContent+=' · '+item.availabilityDate;details.append(stock);
const controls=document.createElement('div');controls.className='basket-controls';
const label=document.createElement('label');label.textContent='Quantité';
const quantity=document.createElement('input');quantity.type='number';quantity.min='1';quantity.max='99';quantity.step='1';quantity.value=item.quantity;quantity.setAttribute('aria-label','Quantité de '+item.article+' chez '+item.store);
quantity.addEventListener('input',()=>{const value=Number(quantity.value);if(!Number.isInteger(value)||value<1||value>99){if(quantity.value!=='')quantity.value=item.quantity;return;}item.quantity=value;persistBasket();sum.textContent=basketMoney.format(item.price*value)+' FCFA';renderBasketTotals();});
quantity.addEventListener('change',()=>{quantity.value=item.quantity;});quantity.addEventListener('blur',()=>{quantity.value=item.quantity;});label.append(quantity);
const sum=document.createElement('strong');sum.textContent=basketMoney.format(subtotal)+' FCFA';
const remove=document.createElement('button');remove.type='button';remove.textContent='Retirer';remove.setAttribute('aria-label','Retirer '+item.article+' chez '+item.store);remove.addEventListener('click',()=>{basket=basket.filter(entry=>entry.id!==item.id);persistBasket();renderBasket();basketNotice.textContent=item.article+' retiré du panier.';});controls.append(label,sum,remove);line.append(details,controls);basketList.append(line);
}
renderBasketTotals();
}
function renderBasketTotals(){
let total=0,count=0;const stores=new Map();
for(const item of basket){const subtotal=item.price*item.quantity;total+=subtotal;count+=item.quantity;stores.set(item.store,(stores.get(item.store)||0)+subtotal);}
if(document.getElementById('basketEmpty'))document.getElementById('basketEmpty').hidden=!!basket.length;
if(document.getElementById('basketTotal'))document.getElementById('basketTotal').textContent=basketMoney.format(total)+' FCFA';
if(document.getElementById('basketCount'))document.getElementById('basketCount').textContent=count+' article'+(count>1?'s':'');
document.getElementById('basketNavCount').textContent=count;const dockCount=document.getElementById('basketDockCount'),dockTotal=document.getElementById('basketDockTotal');if(dockCount)dockCount.textContent=count;const dock=document.querySelector('.basket-dock');if(dock)dock.hidden=count===0;if(dockTotal)dockTotal.textContent=basketMoney.format(total)+' FCFA';
if(document.getElementById('clearBasket'))document.getElementById('clearBasket').disabled=!basket.length;
const breakdown=document.getElementById('basketStores');if(!breakdown)return;breakdown.replaceChildren();
if(stores.size>1){for(const [store,amount] of stores){const row=document.createElement('p');row.textContent=store+' : '+basketMoney.format(amount)+' FCFA';breakdown.append(row);}}
}
document.getElementById('clearBasket')?.addEventListener('click',()=>{basket=[];persistBasket();renderBasket();basketNotice.textContent='Panier vidé.';});
renderBasket();


function syncBasketAvailability(articles){
if(!Array.isArray(articles))return;
for(const item of basket){const row=articles.find(row=>row.article===item.article&&row.supermarche===item.store&&String(row.unite||'unité')===item.format&&String(row.lieu||'')===String(item.place||''));item.availability=row?.disponibilite||'unknown';item.availabilityDate=row?.date_disponibilite||'';}
persistBasket();renderBasket();
}
if(basketList)fetch(document.body.dataset.prices||'./data/articles.json').then(response=>{if(!response.ok)throw new Error();return response.json();}).then(syncBasketAvailability).catch(()=>{basketNotice.textContent='Disponibilité non actualisée. À confirmer en magasin.';});