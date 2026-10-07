'use strict';
let token='',busy=false,proofUrls=[],loadSequence=0;
const el=id=>document.getElementById(id);
function tell(text){el('message').textContent=text;}
async function api(url,options={}){
const response=await fetch(url,{...options,headers:{Authorization:'Bearer '+token,...options.headers}});
const data=await response.json();if(!response.ok)throw new Error(data.message||'Impossible de charger les contributions.');return data;
}
function clearPhotos(){proofUrls.forEach(url=>URL.revokeObjectURL(url));proofUrls=[];}
async function load(){
const sequence=++loadSequence,expectedToken=token;
try{
const data=await api('/api/admin/contributions');const reportData=await api('/api/admin/reports');if(sequence!==loadSequence||expectedToken!==token)return;clearPhotos();el('rows').replaceChildren();el('login').hidden=true;el('toolbar').hidden=false;tell('Contributions chargées.');
if(!data.contributions.length)el('rows').textContent='Aucune contribution reçue.';
const reportHeading=document.createElement('h2');reportHeading.textContent='Signalements des utilisateurs';el('rows').append(reportHeading);
const reasons={wrong_price:'Prix incorrect',unavailable:'Produit indisponible',wrong_format:'Format incorrect',other:'Autre erreur'};
if(!reportData.reports.length){const empty=document.createElement('p');empty.textContent='Aucun signalement reçu.';el('rows').append(empty);}
reportData.reports.forEach(row=>{
const card=document.createElement('article'),heading=document.createElement('h3');heading.textContent=row.article+' · '+row.store;card.append(heading);
const details=document.createElement('p');details.textContent=reasons[row.reason]+' · '+(row.status==='resolved'?'Traité':'À vérifier');card.append(details);
const note=document.createElement('p');note.textContent=row.comment;card.append(note);
if(row.status==='pending'){const button=document.createElement('button');button.textContent='Marquer comme traité';button.addEventListener('click',async()=>{if(busy)return;busy=true;button.disabled=true;try{const result=await api('/api/admin/reports/'+row.id+'/resolve',{method:'POST'});tell(result.message);await load();}catch(error){tell(error.message);}finally{busy=false;button.disabled=false;}});card.append(button);}
el('rows').append(card);
});
const labels={pending:'En attente',approved:'Accepté',rejected:'Refusé'};
data.contributions.forEach(row=>{
const card=document.createElement('article'),title=document.createElement('h2');title.textContent='#'+row.id+' · '+row.article+' · '+labels[row.status];card.append(title);
const description=document.createElement('p');description.textContent=[row.brand,row.variant,row.quantity+' '+row.unit,row.price+' FCFA',row.store,row.location+' · '+(({available:'Disponible',out_of_stock:'Rupture de stock',unknown:'Disponibilité inconnue'})[row.availability]||'Disponibilité inconnue'),'Relevé : '+row.observed_at].filter(Boolean).join(' · ');card.append(description);
if(row.review_note){const reason=document.createElement('p');reason.textContent='Avis enregistré : '+row.review_note;card.append(reason);}
if(row.proof){const photoButton=document.createElement('button');photoButton.className='secondary';photoButton.textContent='Voir la preuve privée';photoButton.addEventListener('click',async()=>{photoButton.disabled=true;try{const response=await fetch('/api/contributions/'+row.id+'/photo',{headers:{Authorization:'Bearer '+token}});if(!response.ok)throw new Error('Photo inaccessible.');const url=URL.createObjectURL(await response.blob());proofUrls.push(url);const image=document.createElement('img');image.src=url;image.alt='Preuve du relevé '+row.id;image.className='proof';card.append(image);}catch(error){tell(error.message);}finally{photoButton.disabled=false;}});card.append(photoButton);}
if(row.status!=='rejected'){
const label=document.createElement('label');label.textContent='Avis au contributeur (obligatoire pour refuser)';const note=document.createElement('textarea');note.maxLength=2000;label.append(note);card.append(label);
const actions=document.createElement('div');actions.className='actions';
const decisions=row.status==='pending'?[['approved','Accepter et publier'],['rejected','Refuser']]:[['rejected','Retirer la validation']];
decisions.forEach(([decision,text])=>{const button=document.createElement('button');button.textContent=text;button.type='button';button.addEventListener('click',async()=>{
if(busy)return;if(decision==='rejected'&&!note.value.trim()){tell('Indiquez un motif de refus ou de retrait.');note.focus();return;}
busy=true;button.disabled=true;
try{const result=await api('/api/admin/contributions/'+row.id+'/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,note:note.value})});tell(result.message);await load();}catch(error){tell(error.message);}finally{busy=false;button.disabled=false;}
});actions.append(button);});card.append(actions);
}
el('rows').append(card);
});
}catch(error){if(sequence===loadSequence&&expectedToken===token)tell(error.message);}
}
el('loginForm').addEventListener('submit',event=>{event.preventDefault();token=el('token').value.trim();el('token').value='';load();});
el('refresh').addEventListener('click',load);
el('logout').addEventListener('click',()=>{if(busy)return;token='';loadSequence++;clearPhotos();el('rows').replaceChildren();el('login').hidden=false;el('toolbar').hidden=true;tell('Session fermée.');});