'use strict';
let csrf='',currentUser=null,registering=false,online=false;
const byId=id=>document.getElementById(id),form=byId('contributionForm'),message=byId('message');
const fields=['article','brand','variant','quantity','unit','price','store','location','observed_at'];
const draftKey='compareprix-contribution-draft-v1';
function tell(text){message.textContent=text;}
async function api(url,options={}){
const response=await fetch(url,{...options,headers:{'X-CSRF-Token':csrf,...options.headers}});
let data;try{data=await response.json();}catch{throw new Error('Les comptes et contributions nécessitent la version serveur de ComparePrix.');}
if(!response.ok)throw new Error(data.message||'La demande a échoué.');return data;
}
function displayAccount(data){csrf=data.csrf;currentUser=data.user;byId('signedIn').hidden=!currentUser;byId('signedOut').hidden=!!currentUser;if(currentUser){byId('greeting').textContent='Bonjour '+currentUser.name;byId('password').value='';}loadHistory();}
async function loadHistory(){
if(!currentUser){byId('historyRows').textContent='Connectez-vous pour suivre vos relevés.';byId('points').textContent='';return;}
try{
const data=await api('/api/contributions');byId('points').textContent=data.points+' points';byId('historyRows').replaceChildren();
if(!data.contributions.length)byId('historyRows').textContent='Vous n’avez pas encore envoyé de relevé.';
const labels={pending:'En attente de validation',approved:'Accepté',rejected:'Refusé'};
data.contributions.forEach(row=>{
const card=document.createElement('article'),title=document.createElement('h3');title.textContent=row.article;card.append(title);
const detail=document.createElement('p');detail.textContent=row.price+' FCFA · '+row.quantity+' '+row.unit+' · '+row.store+' · '+row.location+' · '+row.observed_at;card.append(detail);
const status=document.createElement('p');status.className='badge';status.textContent=labels[row.status];card.append(status);
if(row.review_note){const note=document.createElement('p');note.textContent='Avis : '+row.review_note;card.append(note);}
if(row.proof){const a=document.createElement('a');a.href='/api/contributions/'+row.id+'/photo';a.textContent='Voir ma photo';a.target='_blank';a.rel='noopener';card.append(a);}
byId('historyRows').append(card);
});
}catch(error){tell(error.message);}
}
byId('switchAuth').addEventListener('click',()=>{registering=!registering;byId('registration').hidden=!registering;byId('name').required=registering;byId('password').minLength=registering?12:1;byId('password').autocomplete=registering?'new-password':'current-password';byId('authSubmit').textContent=registering?'Créer mon compte':'Se connecter';byId('switchAuth').textContent=registering?'J’ai déjà un compte':'Créer un compte';});
byId('authForm').addEventListener('submit',async event=>{
event.preventDefault();const button=byId('authSubmit');button.disabled=true;
try{displayAccount(await api('/api/account/'+(registering?'register':'login'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:byId('phone').value,password:byId('password').value,name:byId('name').value})}));tell('Vous êtes connecté. Vous pouvez envoyer votre relevé.');byId('contribution').scrollIntoView({behavior:'smooth'});}catch(error){tell(error.message);}finally{button.disabled=false;}
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
try{const data=await api('/api/contributions',{method:'POST',body:new FormData(form)});tell(data.message);form.reset();try{localStorage.removeItem(draftKey);}catch{}await loadHistory();byId('history').scrollIntoView({behavior:'smooth'});}catch(error){tell(error.message);}finally{byId('send').disabled=false;}
});
if(document.body.dataset.preview==='true'){
tell('Cette version permet de découvrir ComparePrix et de préparer un relevé. La création de compte et l’envoi de prix ne sont pas encore disponibles en ligne.');
byId('authForm').querySelectorAll('input,button').forEach(field=>field.disabled=true);
byId('send').disabled=true;
}else{
api('/api/session').then(data=>{online=true;displayAccount(data);}).catch(error=>{tell(error.message);byId('authSubmit').disabled=true;byId('send').disabled=true;});
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
