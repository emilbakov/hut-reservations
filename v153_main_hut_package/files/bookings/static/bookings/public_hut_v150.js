/* v150 booking feedback: preserve details, review quantities and full stay price. */
document.addEventListener('DOMContentLoaded',()=>{
 'use strict';
 const form=document.getElementById('ph-reservation-form'),dates=document.getElementById('ph-date-form'),party=document.getElementById('ph-party-size'),dateParty=document.getElementById('ph-search-guests');
 const $=id=>document.getElementById(id),fields=()=>Array.from(form?.querySelectorAll('input.beds')||[]),currency=form?.dataset.currency||'€';
 const ui=window.SummitDeskUI,t=ui?.text||((s,v={})=>s.replace(/%\((\w+)\)s/g,(m,k)=>v[k]??m));
 const amount=ui?.amount||(v=>new Intl.NumberFormat(document.documentElement.lang||'en',{useGrouping:false,minimumFractionDigits:2,maximumFractionDigits:2}).format(v)),money=v=>amount(v)+' '+currency;
 let controller=null;
 document.querySelectorAll('.ph-field-errors').forEach((error,i)=>{const field=error.closest('.ph-guest-field,.ph-room-action,.ph-date-field')?.querySelector('input,textarea,select');if(field){error.id||='ph-error-'+i;field.setAttribute('aria-describedby',((field.getAttribute('aria-describedby')||'')+' '+error.id).trim());field.setAttribute('aria-invalid','true');}});
 const errorSummary=document.getElementById('sd150-errors');if(!errorSummary||errorSummary.hidden){const localError=document.querySelector('.ph-error-box');if(localError){localError.tabIndex=-1;localError.focus();}}
 function summary(){
  if(!form||!party)return;
  const nights=Number(form.dataset.nights),target=Number(party.value);let selected=0,total=0,invalid=false;
  $('ph-summary-lines').replaceChildren();
  fields().forEach(input=>{
   const qty=Number(input.value||0),price=Number(input.dataset.price);
   if(!Number.isInteger(qty)||qty<0||qty>Number(input.max))invalid=true;
   const count=Number.isInteger(qty)?Math.max(0,qty):0,subtotal=Math.round(price*100)*count*nights;
   selected+=count;total+=subtotal;
   input.closest('[data-room-id]').classList.toggle('ph-room-selected',count>0);
   const controls=input.closest('.ph-quantity');controls.querySelector('[data-quantity="-1"]').disabled=count<=0;controls.querySelector('[data-quantity="1"]').disabled=count>=Number(input.max);
   if(count){const li=document.createElement('li'),label=document.createElement('span'),value=document.createElement('strong');label.textContent=input.closest('[data-room-name]').dataset.roomName+' · '+count+' × '+money(price)+' × '+nights+' '+t(nights===1?'night':'nights');value.textContent=money(subtotal/100);li.append(label,value);$('ph-summary-lines').append(li);}
  });
  if(!selected){const li=document.createElement('li');li.textContent=t('Choose beds from the rooms above.');$('ph-summary-lines').append(li);}
  const valid=Number.isInteger(target)&&target>=1&&target<=30,remaining=target-selected;
  const status=$('ph-selection-status');status.textContent=invalid?t('Some quantities exceed availability. Adjust the room selections.'):!valid?t('Choose between 1 and 30 guests.'):remaining>0?t('%(selected)s of %(target)s beds selected. Choose %(remaining)s more.',{selected,target,remaining}):remaining<0?t('You selected %(selected)s beds for %(target)s guests. Adjust beds or update your group size.',{selected,target}):t('All %(target)s beds selected. Review your details and send the request.',{target});
  status.classList.toggle('warning',invalid||!valid||remaining!==0);
  $('ph-request-submit').disabled=form.getAttribute('aria-busy')==='true'||form.dataset.sending==='true';
  $('ph-request-submit').textContent=form.dataset.sending==='true'?t('Sending request…'):t('Request reservation →');
  $('ph-total').textContent=amount(total/100);if($('ph-total-prompt'))$('ph-total-prompt').hidden=selected>0;if($('ph-total-value'))$('ph-total-value').hidden=selected===0;$('ph-mobile-count').textContent=t('%(selected)s of %(target)s beds',{selected,target:valid?target:'—'});$('ph-mobile-total').textContent=selected?money(total/100):t('Choose beds to see the total');$('ph-mobile-total').classList.toggle('ph-total-prompt',selected===0);
  if(dateParty&&valid&&form.getAttribute('aria-busy')!=='true')dateParty.value=party.value;
 }
 async function refresh(){
  if(!form||!dates||!dates.reportValidity())return;
  controller?.abort();const current=new AbortController();controller=current;
  const check=dates.querySelector('button[type="submit"]'),status=$('ph-availability-status');check.disabled=true;form.setAttribute('aria-busy','true');summary();status.textContent=t('Checking availability. Your guest details are kept.');
  const url=new URL(dates.action);new FormData(dates).forEach((v,k)=>url.searchParams.set(k,v));
  try{
   const response=await fetch(url,{credentials:'same-origin',signal:current.signal,headers:{'X-Requested-With':'XMLHttpRequest'}});if(!response.ok)throw new Error('Availability failed');
   const freshDoc=new DOMParser().parseFromString(await response.text(),'text/html'),fresh=freshDoc.getElementById('ph-reservation-form');
   if(!fresh){const serverErrors=freshDoc.getElementById('sd150-errors');if(serverErrors&&!serverErrors.hidden&&errorSummary){errorSummary.replaceChildren(...serverErrors.childNodes);errorSummary.hidden=false;errorSummary.focus({preventScroll:true});errorSummary.scrollIntoView({block:'start'});}const errors=Array.from(freshDoc.querySelectorAll('.ph-field-errors,.ph-error-box')).map(x=>x.textContent.trim()).join(' ');status.textContent=(errors||t('Check your dates.'))+' '+t('Your previous selection is kept.');return;}
   if(errorSummary)errorSummary.hidden=true;const previous=Object.fromEntries(fields().map(x=>[x.name,Number(x.value||0)]));$('ph-room-list').replaceChildren(...freshDoc.getElementById('ph-room-list').childNodes);
   const present=new Set(fields().map(x=>x.name));let reduced=Object.entries(previous).some(([n,q])=>q>0&&!present.has(n));
   fields().forEach(x=>{const q=previous[x.name]||0;x.value=String(Math.min(q,Number(x.max)));if(q>Number(x.max))reduced=true;});
   ['check_in','check_out','submission_token'].forEach(n=>{form.querySelector('[name="'+n+'"]').value=fresh.querySelector('[name="'+n+'"]').value;});form.dataset.nights=fresh.dataset.nights;
   ['ph-review-dates','ph-night-count','ph-booking-result','ph-alternatives','ph-fully-booked-msg'].forEach(id=>{if($(id)&&freshDoc.getElementById(id))$(id).replaceChildren(...freshDoc.getElementById(id).childNodes);});
   const banner=document.querySelector('.ph-stay-banner'),freshBanner=freshDoc.querySelector('.ph-stay-banner');if(banner&&freshBanner)banner.replaceChildren(...freshBanner.childNodes);
   $('guest-details').hidden=freshDoc.getElementById('guest-details').hidden;$('ph-mobile-review').hidden=freshDoc.getElementById('ph-mobile-review').hidden;
   party.value=dateParty.value;window.history.replaceState({},'',url.pathname+url.search);status.textContent=t('Availability updated. Review your beds.')+(reduced?' '+t('Some quantities were reduced to match availability.'):'');
  }catch(error){if(error.name!=='AbortError')status.textContent=t('Could not refresh availability. Your details are kept. Please try again.');}
  finally{if(controller===current){check.disabled=false;form.removeAttribute('aria-busy');summary();}}
 }
 if(form){
  form.addEventListener('input',e=>{if(e.target.matches('input.beds,#ph-party-size'))summary();});form.addEventListener('change',summary);
  form.addEventListener('click',e=>{
   const step=e.target.closest('[data-quantity]');if(step){const input=$(step.dataset.for);input.value=String(Math.max(0,Math.min(Number(input.max),Number(input.value||0)+Number(step.dataset.quantity))));summary();}
   const choice=e.target.closest('[data-select-room]');if(choice){fields().forEach(x=>{x.value=x.closest('[data-room-id]').dataset.roomId===choice.dataset.selectRoom?party.value:'0';});summary();$('ph-review').scrollIntoView({block:'start'});}
   const alternative=e.target.closest('[data-apply-stay]');if(alternative&&dates){e.preventDefault();dates.querySelector('[name="check_in"]').value=alternative.dataset.checkIn;dates.querySelector('[name="check_out"]').value=alternative.dataset.checkOut;refresh();}
  });
  form.addEventListener('submit',e=>{if(e.submitter?.name==='preview_stay')return;if($('ph-request-submit').disabled||form.dataset.sending==='true'){e.preventDefault();return;}form.dataset.sending='true';$('ph-request-submit').disabled=true;$('ph-request-submit').textContent=t('Sending request…');});summary();window.addEventListener('pageshow',event=>{if(event.persisted){delete form.dataset.sending;form.removeAttribute('aria-busy');summary();}});
 }
 if(dates){const arrival=dates.querySelector('[name="check_in"]'),departure=dates.querySelector('[name="check_out"]');
  function minDeparture(){if(!arrival.value)return;const next=new Date(arrival.value+'T00:00:00Z');if(Number.isNaN(next.getTime()))return;next.setUTCDate(next.getUTCDate()+1);departure.min=next.toISOString().slice(0,10);if(departure.value&&departure.value<departure.min)departure.value='';}
  arrival.addEventListener('change',minDeparture);minDeparture();dates.addEventListener('submit',e=>{if(form){e.preventDefault();refresh();}});
 }
});
