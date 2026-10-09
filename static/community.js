'use strict';
const pageMode=document.body.dataset.page||'account';
function contributionDestination(){const target=new URL('./contribuer.html',location.href);target.search=location.search;target.hash='contribution';return target.href;}
function accountDestination(){const target=new URL('./compte.html',location.href);target.search=location.search;if(!target.searchParams.has('intent'))target.searchParams.set('intent','contribute');return target.href;}
let csrf='',currentUser=null,registering=true,online=false,features={email:false,require_verified_email:false},pendingEmail='';
const byId=id=>document.getElementById(id),form=byId('contributionForm'),message=byId('message');
const fields=['article','brand','variant','quantity','unit','price','store','location','city','district','shop','observed_at','availability'];
const draftKey='compareprix-contribution-draft-v1';
function tell(text){message.textContent=text;}
async function api(url,options={}){
const response=await fetch(url,{...options,headers:{'X-CSRF-Token':csrf,...options.headers}});
let data;try{data=await response.json();}catch{throw new Error('Les comptes et contributions nécessitent la version serveur de ComparePrix.');}
if(!response.ok)throw new Error(data.message||'La demande a échoué.');return data;
}
function displayAccount(data){csrf=data.csrf;currentUser=data.user;if(data.features)features=data.features;renderEmail();byId('signedIn').hidden=!currentUser;byId('signedOut').hidden=!!currentUser;byId('contribution').hidden=!currentUser||pageMode!=='contribution';if(pageMode==='contribution'&&!currentUser){location.replace(accountDestination());return;}byId('contributeFromAccount').href=contributionDestination();document.querySelector('.account-layout').classList.toggle('account-first',!currentUser);if(currentUser){byId('greeting').textContent='Bonjour '+currentUser.name;byId('password').value='';}loadHistory();}
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
function showAuthMode(){byId('registration').hidden=!registering;byId('name').required=false;byId('consent').required=registering;byId('password').minLength=registering?12:1;byId('password').autocomplete=registering?'new-password':'current-password';byId('authSubmit').textContent=registering?'Créer mon compte':'Se connecter';byId('switchAuth').textContent=registering?'J’ai déjà un compte':'Créer un compte';}
byId('switchAuth').addEventListener('click',()=>{registering=!registering;showAuthMode();});
byId('showPassword')?.addEventListener('click',()=>{const password=byId('password'),visible=password.type==='password';password.type=visible?'text':'password';byId('showPassword').textContent=visible?'Masquer le mot de passe':'Afficher le mot de passe';byId('showPassword').setAttribute('aria-pressed',String(visible));});
showAuthMode();
function renderEmail(){
const box=byId('emailBox'),forgot=byId('forgotBox');if(!box||!forgot)return;
box.hidden=!(currentUser&&features.email);forgot.hidden=!(features.email&&!currentUser);
if(currentUser){byId('emailState').textContent=currentUser.email_verified?'Email vérifié : '+currentUser.email+'. Il permet de récupérer votre mot de passe.':'Aucun email vérifié : sans lui, votre mot de passe ne peut pas être récupéré.'+(features.require_verified_email?' Il est requis pour envoyer un prix.':'');byId('emailForm').hidden=false;byId('emailCodeForm').hidden=!pendingEmail;byId('emailSend').textContent=currentUser.email_verified?'Changer d’email':'Envoyer le code';}
}
async function post(url,payload){return api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});}
byId('emailForm')?.addEventListener('submit',async event=>{event.preventDefault();const button=byId('emailSend');button.disabled=true;
try{const email=byId('emailInput').value.trim();const data=await post('/api/account/email/request',{email});pendingEmail=email;byId('emailCodeForm').hidden=false;byId('emailCode').focus();tell(data.message);}catch(error){tell(error.message);}finally{button.disabled=false;}});
byId('emailCodeForm')?.addEventListener('submit',async event=>{event.preventDefault();const button=byId('emailConfirm');button.disabled=true;
try{const data=await post('/api/account/email/confirm',{email:pendingEmail,code:byId('emailCode').value.trim()});pendingEmail='';byId('emailCode').value='';byId('emailInput').value='';currentUser={...currentUser,email_verified:true,email:data.email};renderEmail();tell(data.message);}catch(error){tell(error.message);}finally{button.disabled=false;}});
byId('forgotBtn')?.addEventListener('click',()=>{const form=byId('resetForm'),open=form.hidden;form.hidden=!open;byId('forgotBtn').setAttribute('aria-expanded',String(open));if(open){byId('resetPhone').value=byId('phone').value;byId('resetPhone').focus();}});
byId('resetSend')?.addEventListener('click',async()=>{const button=byId('resetSend');button.disabled=true;
try{const data=await post('/api/account/reset/request',{phone:byId('resetPhone').value});tell(data.message);byId('resetCode').focus();}catch(error){tell(error.message);}finally{button.disabled=false;}});
byId('resetForm')?.addEventListener('submit',async event=>{event.preventDefault();
try{const data=await post('/api/account/reset/confirm',{phone:byId('resetPhone').value,code:byId('resetCode').value.trim(),password:byId('resetPassword').value});csrf=data.csrf;byId('resetForm').reset();byId('resetForm').hidden=true;registering=false;showAuthMode();byId('phone').focus();tell(data.message);}catch(error){tell(error.message);}});
byId('authForm').addEventListener('submit',async event=>{
event.preventDefault();const button=byId('authSubmit');button.disabled=true;
try{displayAccount(await api('/api/account/'+(registering?'register':'login'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:byId('phone').value,password:byId('password').value,name:byId('name').value,consent:registering&&byId('consent').checked})}));tell('Vous êtes connecté. Vous pouvez envoyer votre relevé.');if(['update','contribute'].includes(new URLSearchParams(location.search).get('intent')))location.assign(contributionDestination());else byId('account').scrollIntoView({behavior:'smooth'});}catch(error){tell(error.message);}finally{button.disabled=false;}
});
byId('logout').addEventListener('click',async()=>{try{displayAccount(await api('/api/account/logout',{method:'POST'}));tell('Vous êtes déconnecté.');}catch(error){tell(error.message);}});
// Réduit la photo avant l'envoi : moins de données mobiles consommées, envoi plus fiable. En cas de doute on garde l'original.
async function shrinkPhoto(file){
if(file.size<=400*1024||!/^image\/(jpeg|png)$/.test(file.type)||!window.createImageBitmap)return file;
try{const bitmap=await createImageBitmap(file,{imageOrientation:'from-image'}),scale=Math.min(1,1600/Math.max(bitmap.width,bitmap.height)),canvas=document.createElement('canvas');
canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close?.();
const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',0.8));
return blob&&blob.size<file.size?new File([blob],'photo.jpg',{type:'image/jpeg'}):file;}catch{return file;}
}
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
byId('send').disabled=true;
try{const body=new FormData(form),original=byId('photo').files[0];
if(original){const photo=await shrinkPhoto(original);if(photo.size>5*1024*1024){tell('La photo dépasse 5 Mo, même réduite. Choisissez-en une autre.');return;}body.set('photo',photo,photo.name);}
const data=await api('/api/contributions',{method:'POST',body});tell(data.message);form.reset();try{localStorage.removeItem(draftKey);}catch{}await loadHistory();location.assign('./compte.html#history');}catch(error){tell(error.message);}finally{byId('send').disabled=false;}
});
if(document.body.dataset.preview==='true'){
if(pageMode==='contribution'){location.replace(accountDestination());}
tell('La création de compte et l’envoi de prix ne sont pas encore disponibles sur cette démonstration en ligne.');
byId('authForm').querySelectorAll('input,button').forEach(field=>field.disabled=true);
byId('send').disabled=true;
}else{
api('/api/session').then(data=>{online=true;displayAccount(data);if(pageMode==='account'&&data.user&&['update','contribute'].includes(new URLSearchParams(location.search).get('intent')))location.assign(contributionDestination());}).catch(error=>{tell(error.message);byId('authSubmit').disabled=true;byId('send').disabled=true;});
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
byId('switchAuth').click();
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