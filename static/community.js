'use strict';
const merchantMode=document.body.dataset.merchant==='true';
const pageMode=document.body.dataset.page||'account';
function contributionDestination(){const target=new URL(merchantMode||new URLSearchParams(location.search).get('intent')==='merchant'?'./commercant.html':'./contribuer.html',location.href);target.search=location.search;target.hash='contribution';return target.href;}
function accountDestination(){const target=new URL('./compte.html',location.href);target.search=location.search;if(merchantMode)target.searchParams.set('intent','merchant');else if(!target.searchParams.has('intent'))target.searchParams.set('intent','contribute');return target.href;}
let csrf='',currentUser=null,registering=true,online=false;
const byId=id=>document.getElementById(id),form=byId('contributionForm'),message=byId('message');
const fields=['article','brand','variant','quantity','unit','price','store','location','city','district','shop','observed_at','availability'];
const draftKey='compareprix-contribution-draft-v1';
function tell(text){message.textContent=text;}
async function api(url,options={}){
const response=await fetch(url,{...options,headers:{'X-CSRF-Token':csrf,...options.headers}});
let data;try{data=await response.json();}catch{throw new Error('Les comptes et contributions nécessitent la version serveur de ComparePrix.');}
if(!response.ok)throw new Error(data.message||'La demande a échoué.');return data;
}
function displayAccount(data){byId('history').hidden=!data.user;csrf=data.csrf;currentUser=data.user;byId('signedIn').hidden=!currentUser;byId('signedOut').hidden=!!currentUser;byId('contribution').hidden=!currentUser||pageMode!=='contribution';if(pageMode==='contribution'&&!currentUser){location.replace(accountDestination());return;}byId('contributeFromAccount').href=contributionDestination();document.querySelector('.account-layout').classList.toggle('account-first',!currentUser);if(currentUser){byId('greeting').textContent='Bonjour '+currentUser.name;byId('password').value='';}loadHistory();if(currentUser&&merchantMode)loadMerchantProfile();}
async function loadHistory(){
if(!currentUser){byId('historyRows').textContent='Connectez-vous pour suivre vos relevés.';byId('points').textContent='';return;}
try{
const data=await api('/api/contributions');byId('points').textContent=data.points+' points';byId('historyRows').replaceChildren();
if(!data.contributions.length)byId('historyRows').textContent='Vous n’avez pas encore envoyé de relevé.';
const labels={pending:'En attente de validation',approved:'Accepté',rejected:'Refusé'};
data.contributions.forEach(row=>{
const card=document.createElement('article'),title=document.createElement('h3');title.textContent=row.article;card.append(title);
const detail=document.createElement('p');detail.textContent=row.price+' FCFA · '+row.quantity+' '+row.unit+' · '+row.store+' · '+row.location+' · '+row.observed_at;card.append(detail);
const stock=document.createElement('p');stock.textContent=({available:'🟢 Disponible',out_of_stock:'🔴 Rupture de stock',unknown:'⚪ Disponibilité inconnue'})[row.availability]||'⚪ Disponibilité inconnue';card.append(stock);const status=document.createElement('p');status.className='badge';status.textContent=labels[row.status];card.append(status);
if(row.review_note){const note=document.createElement('p');note.textContent='Avis : '+row.review_note;card.append(note);}
if(row.proof){const a=document.createElement('a');a.href='/api/contributions/'+row.id+'/photo';a.textContent='Voir ma photo';a.target='_blank';a.rel='noopener';card.append(a);}
byId('historyRows').append(card);
});
}catch(error){tell(error.message);}
}
function showAuthMode(){byId('registration').hidden=!registering;byId('name').required=false;byId('password').minLength=registering?12:1;byId('password').autocomplete=registering?'new-password':'current-password';byId('authSubmit').textContent=registering?'Créer mon compte':'Se connecter';byId('switchAuth').textContent=registering?'J’ai déjà un compte':'Créer un compte';}
byId('switchAuth').addEventListener('click',()=>{registering=!registering;showAuthMode();});
byId('showPassword')?.addEventListener('click',()=>{const password=byId('password'),visible=password.type==='password';password.type=visible?'text':'password';byId('showPassword').textContent=visible?'Masquer le mot de passe':'Afficher le mot de passe';byId('showPassword').setAttribute('aria-pressed',String(visible));});
showAuthMode();
byId('authForm').addEventListener('submit',async event=>{
event.preventDefault();const button=byId('authSubmit');button.disabled=true;
try{displayAccount(await api('/api/account/'+(registering?'register':'login'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:byId('phone').value,password:byId('password').value,name:byId('name').value})}));tell('Vous êtes connecté. Vous pouvez envoyer votre relevé.');if(['update','contribute','merchant'].includes(new URLSearchParams(location.search).get('intent')))location.assign(contributionDestination());else byId('account').scrollIntoView({behavior:'smooth'});}catch(error){tell(error.message);}finally{button.disabled=false;}
});
byId('logout').addEventListener('click',async()=>{try{displayAccount(await api('/api/account/logout',{method:'POST'}));tell('Vous êtes déconnecté.');}catch(error){tell(error.message);}});
function saveDraft(){try{localStorage.setItem(draftKey,JSON.stringify(Object.fromEntries(fields.map(key=>[key,byId(key).value]))));}catch{byId('draftNote').textContent='Le navigateur ne peut pas conserver ce brouillon.';}}
form.addEventListener('input',saveDraft);
try{const draft=JSON.parse(localStorage.getItem(draftKey)||'{}');fields.forEach(key=>{if(typeof draft[key]==='string')byId(key).value=draft[key];});}catch{}
const today=new Date();const dateText=value=>value.getFullYear()+'-'+String(value.getMonth()+1).padStart(2,'0')+'-'+String(value.getDate()).padStart(2,'0');
byId('observed_at').max=dateText(today);const earliest=new Date(today);earliest.setDate(earliest.getDate()-30);byId('observed_at').min=dateText(earliest);if(!byId('observed_at').value)byId('observed_at').value=dateText(today);
byId('clearDraft').addEventListener('click',()=>{form.reset();try{localStorage.removeItem(draftKey);}catch{}tell('Brouillon effacé.');});
form.addEventListener('submit',async event=>{
event.preventDefault();
if(!online){tell('Cette page nécessite un serveur ComparePrix pour envoyer des relevés.');return;}
if(!currentUser){tell('Connectez-vous ou créez un compte pour envoyer ce relevé. Votre brouillon est conservé.');byId('account').scrollIntoView({behavior:'smooth'});return;}
const photo=byId('photo').files[0];if(photo&&photo.size>5*1024*1024){tell('La photo dépasse 5 Mo.');return;}
byId('send').disabled=true;
try{const data=await api('/api/contributions',{method:'POST',body:new FormData(form)});tell(data.message);form.reset();try{localStorage.removeItem(draftKey);}catch{}await loadHistory();location.assign('./compte.html#history');}catch(error){tell(error.message);}finally{byId('send').disabled=false;}
});
if(document.body.dataset.preview==='true'){
if(pageMode==='contribution'){location.replace(accountDestination());}
tell('La création de compte et l’envoi de prix ne sont pas encore disponibles sur cette démonstration en ligne.');
byId('authForm').querySelectorAll('input,button').forEach(field=>field.disabled=true);
byId('send').disabled=true;
}else{
api('/api/session').then(data=>{online=true;displayAccount(data);if(pageMode==='account'&&data.user&&['update','contribute','merchant'].includes(new URLSearchParams(location.search).get('intent')))location.assign(contributionDestination());}).catch(error=>{tell(error.message);byId('authSubmit').disabled=true;byId('send').disabled=true;});
}



const incoming=new URLSearchParams(location.search);
if(incoming.has('article')){
byId('article').value=incoming.get('article').slice(0,200);
byId('store').value=(incoming.get('store')||'').slice(0,120);
byId('location').value=(incoming.get('location')||'').slice(0,200);
const format=(incoming.get('format')||'').match(/^\s*(?:(\d+(?:[.,]\d+)?)\s*)?(kg|g|ml|L|pièce)\s*$/);
if(format){byId('quantity').value=(format[1]||'1').replace(',','.');byId('unit').value=format[2];}
byId('price').value='';byId('photo').value='';saveDraft();
}

document.querySelectorAll('a[href="#contribution"]').forEach(link=>link.addEventListener('click',event=>{if(!currentUser){event.preventDefault();byId('account').scrollIntoView({behavior:'smooth'});tell('Créez votre compte ou connectez-vous avant de renseigner le prix.');}}));
if(new URLSearchParams(location.search).get('intent')==='update'||new URLSearchParams(location.search).get('intent')==='contribute'){
registering=true;showAuthMode();
}
document.querySelector('.account-layout').classList.toggle('account-first',!currentUser);

let locationCatalog={cities:['Abidjan'],locations:[]};
const normalizePlace=value=>String(value||'').trim().toLocaleLowerCase('fr');
function options(id,values){byId(id).replaceChildren(...[...new Set(values.filter(Boolean))].sort((a,b)=>a.localeCompare(b,'fr')).map(value=>new Option(value,value)));}
function updatePlaceSuggestions(){
const city=normalizePlace(byId('city').value),district=normalizePlace(byId('district').value),store=normalizePlace(byId('store').value);
options('cityOptions',[...(locationCatalog.cities||[]),...locationCatalog.locations.map(row=>row.city)]);
options('districtOptions',[...(locationCatalog.communesByCity?.[Object.keys(locationCatalog.communesByCity||{}).find(key=>normalizePlace(key)===city)]||locationCatalog.communes||[]),...locationCatalog.locations.filter(row=>normalizePlace(row.city)===city).map(row=>row.district)]);
options('shopOptions',locationCatalog.locations.filter(row=>normalizePlace(row.city)===city&&normalizePlace(row.district)===district&&(!store||normalizePlace(row.store)===store)).map(row=>row.shop));
byId('district').disabled=!city;byId('shop').disabled=!city||!district;
byId('locationHelp').textContent=city && !Object.keys(locationCatalog.communesByCity||{}).some(key=>normalizePlace(key)===city) ? 'Choisissez la commune du lieu dans la liste nationale. Les boutiques proposées dépendent de votre sélection.' : 'Choisissez la ville, puis la commune et la boutique. Vous pouvez saisir une boutique absente de la liste.';
byId('location').value=['city','district','shop'].map(key=>byId(key).value.trim()).filter(Boolean).join(' · ');
}
byId('city').addEventListener('input',()=>{byId('district').value='';byId('shop').value='';updatePlaceSuggestions();saveDraft();});
byId('district').addEventListener('input',()=>{byId('shop').value='';updatePlaceSuggestions();saveDraft();});
byId('store').addEventListener('input',()=>{byId('shop').value='';updatePlaceSuggestions();saveDraft();});
byId('shop').addEventListener('input',()=>{updatePlaceSuggestions();saveDraft();});
form.addEventListener('reset',()=>setTimeout(updatePlaceSuggestions,0));
['city','district','shop'].forEach(key=>{if(incoming.get(key))byId(key).value=incoming.get(key).slice(0,key==='city'?50:key==='district'?60:80);});
updatePlaceSuggestions();
fetch(document.body.dataset.preview==='true'?'./static/locations.json':'/api/locations').then(response=>{if(!response.ok)throw new Error();return response.json();}).then(data=>{if(Array.isArray(data.locations)){locationCatalog=data;updatePlaceSuggestions();}}).catch(()=>{byId('locationHelp').textContent='Les suggestions ne sont pas disponibles pour le moment. Saisissez la ville, la commune et la boutique dans leurs champs séparés.';});
if(merchantMode){
document.querySelector('.page-title h1').textContent='🏪 Mon espace commerçant';
document.querySelector('.page-title p').textContent='Votre boutique, vos prix et vos disponibilités.';
document.querySelector('#contribution > h2').textContent='Ajouter un prix de ma boutique';
byId('saveMerchantProfile').addEventListener('click',async()=>{
const button=byId('saveMerchantProfile');button.disabled=true;
try{const result=await api('/api/merchant/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(['store','city','district','shop'].map(key=>[key,byId(key).value])))});tell(result.message);}
catch(error){tell(error.message);}finally{button.disabled=false;}
});

}

function loadMerchantProfile(){api('/api/merchant/profile').then(data=>{if(data.profile){['store','city','district','shop'].forEach(key=>{if(!byId(key).value)byId(key).value=data.profile[key]||'';});updatePlaceSuggestions();}}).catch(error=>tell(error.message));}

const merchantIntent=merchantMode||new URLSearchParams(location.search).get('intent')==='merchant';
if(pageMode==='account'&&merchantIntent){
 document.querySelector('.page-title h1').textContent='🏪 Votre boutique sur ComparePrix';
 document.querySelector('.page-title p').textContent='Créez votre compte pour proposer vos produits.';
 document.querySelector('#account h2').textContent='📱 Commençons par votre compte';
 document.querySelector('.visual-help h2').textContent='Vos produits, près des clients';
 document.querySelector('.visual-help > p').textContent='🏪 Boutique → 📦 Produits → ✅ Validation';
}
if(pageMode==='contribution'){
 const steps=[...form.querySelectorAll('fieldset.form-group-step')];
 let step=0;
 const progress=document.createElement('div');progress.className='form-progress';progress.setAttribute('aria-label','Étapes du formulaire');
 steps.forEach((fieldset,i)=>{const badge=document.createElement('span');badge.textContent=(i+1)+' · '+fieldset.querySelector('legend').textContent.replace(/^[^·]*·\s*/,'');progress.append(badge);});
 form.prepend(progress);
 const controls=document.createElement('div');controls.className='wizard-actions';
 const previous=document.createElement('button');previous.type='button';previous.className='secondary';previous.textContent='← Retour';
 const next=document.createElement('button');next.type='button';next.textContent='Continuer →';controls.append(previous,next);form.append(controls);
 function showStep(){steps.forEach((fieldset,i)=>fieldset.hidden=i!==step);[...progress.children].forEach((badge,i)=>{badge.classList.toggle('active',i===step);if(i===step)badge.setAttribute('aria-current','step');else badge.removeAttribute('aria-current');});previous.hidden=step===0;next.hidden=step===steps.length-1;byId('send').hidden=step!==steps.length-1;}
 previous.addEventListener('click',()=>{step--;showStep();progress.scrollIntoView({block:'center'});});
 next.addEventListener('click',()=>{for(const input of steps[step].querySelectorAll('input,select,textarea')){if(!input.checkValidity()){input.reportValidity();return;}}step++;showStep();progress.scrollIntoView({block:'center'});});
 form.addEventListener('invalid',event=>{const fieldset=event.target.closest('fieldset');if(fieldset){step=steps.indexOf(fieldset);showStep();}},true);
 showStep();
}
