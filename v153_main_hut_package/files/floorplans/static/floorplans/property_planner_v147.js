/* v147: property-scoped calendar interactions, using only authorized rendered data. */
(()=>{'use strict';
 const root=document.getElementById('sd140');if(!root)return;
 const $=id=>document.getElementById(id),form=$('sd140-form'),room=$('sd140-room'),arrival=$('sd140-in'),departure=$('sd140-out'),beds=$('sd140-beds'),status=$('sd140-status'),submit=$('sd140-submit'),board=$('sd142-grid'),scroll=$('sd140-scroll');
 const rows=Array.from(board.querySelectorAll('.sd142-roomrow')),heads=Array.from(board.querySelectorAll('.sd142-dayhead')),cells=Array.from(board.querySelectorAll('.sd142-day')),today=root.dataset.today,currency=root.dataset.currency;
 const ui=window.SummitDeskUI,t=ui?.text||((s,v={})=>s.replace(/%\((\w+)\)s/g,(m,k)=>v[k]??m));
 const utc=d=>Date.parse(d+'T00:00:00Z'),iso=t=>new Date(t).toISOString().slice(0,10),fmt=ui?.date||(d=>d?new Date(utc(d)).toLocaleDateString(document.documentElement.lang||'en',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}):''),money=v=>(ui?.amount?ui.amount(v):new Intl.NumberFormat(document.documentElement.lang||'en',{useGrouping:false,minimumFractionDigits:2,maximumFractionDigits:2}).format(v))+' '+currency;
 const daysBetween=(a,b)=>Math.round((utc(b)-utc(a))/86400000);
 const dayMaps=new Map(rows.map(r=>[r.dataset.room,new Map(Array.from(r.querySelectorAll('.sd142-day')).map(c=>[c.dataset.day,c]))]));
 const entries=new Map(rows.map(r=>{const map=new Map();r.querySelectorAll('.sd142-booking-data').forEach(el=>{if(!map.has(el.dataset.code))map.set(el.dataset.code,{...el.dataset});});return [r.dataset.room,Array.from(map.values())];}));
 let awaitingEnd=Boolean(arrival.value&&!departure.value),offset=0,windowCount=heads.length,previewTrigger=null;
 root.classList.add('sd146-enhanced');$('sd146-window-controls').hidden=false;
 function available(row,a,b,q){
  if(!row||row.dataset.active!=='1'||!Number.isInteger(q)||q<1||q>Number(row.dataset.capacity))return false;
  const n=daysBetween(a,b);if(!Number.isFinite(n)||n<1||n>Number(root.dataset.maxNights)||a<today||a>root.dataset.latestArrival)return false;
  const map=dayMaps.get(row.dataset.room);for(let i=0;i<n;i++){const c=map.get(iso(utc(a)+i*86400000));if(!c||Number(c.dataset.free)<q)return false;}return true;
 }
 function alternatives(a,b,q,error){
  const box=$('sd146-alternatives');box.replaceChildren();box.hidden=true;
  if(!error||!a||!b||!Number.isInteger(q)||q<1||daysBetween(a,b)<1)return;
  const choices=[];
  rows.forEach(r=>{if(r.dataset.room!==room.value&&available(r,a,b,q))choices.push({row:r,a,b});});
  const chosen=rows.find(r=>r.dataset.room===room.value);
  if(chosen){for(const shift of [1,-1,2,-2,3,-3]){const x=iso(utc(a)+shift*86400000),y=iso(utc(b)+shift*86400000);if(available(chosen,x,y,q))choices.push({row:chosen,a:x,b:y});if(choices.length>=3)break;}}
  if(!choices.length)return;
  box.hidden=false;const title=document.createElement('p');title.textContent=t('Available alternatives — your guest details are kept:');box.append(title);
  choices.slice(0,3).forEach(choice=>{const button=document.createElement('button');button.type='button';button.textContent=choice.row.dataset.name+' · '+fmt(choice.a)+' – '+fmt(choice.b)+' · '+money(Math.round(Number(choice.row.dataset.price)*100)*q*daysBetween(choice.a,choice.b)/100);button.addEventListener('click',()=>{room.value=choice.row.dataset.room;arrival.value=choice.a;departure.value=choice.b;awaitingEnd=false;showSelection();validate();});box.append(button);});
 }
 function validate(){
  const row=rows.find(r=>r.dataset.room===room.value),q=Number(beds.value),a=arrival.value,b=departure.value,n=daysBetween(a,b);let error='',message='';
  if(!row)message=t('Choose a room or click an available arrival.');
  else if(!a)message=t('Choose your arrival date.');
  else if(a<today||a>root.dataset.latestArrival)error=t('Choose an arrival within the permitted booking period.');
  else if(!b)message=t('Arrival: %(date)s. Choose a later departure in this room.',{date:fmt(a)});
  else if(!Number.isFinite(n)||n<1)error=t('Departure must be after arrival.');
  else if(n>Number(root.dataset.maxNights))error=t('Choose a stay of up to %(count)s nights.',{count:root.dataset.maxNights});
  else if(!Number.isInteger(q)||q<1||q>Number(row.dataset.capacity))error=t('Guests must be between 1 and %(count)s for this room.',{count:row.dataset.capacity});
  else{let checked=0;for(const [day,cell] of dayMaps.get(row.dataset.room)){if(day>=a&&day<b){checked++;if(Number(cell.dataset.free)<q){error=t('Not enough beds on %(date)s. Choose an alternative below or adjust your stay.',{date:fmt(day)});break;}}}
   if(!error)message=checked<n?t('Some nights are outside this calendar. Full availability is checked when you confirm.'):t('Available for %(count)s %(unit)s · checkout is not charged.',{count:n,unit:t(n===1?'night':'nights')});
  }
  const valid=Boolean(row&&a&&b&&!error&&n>0),total=row&&n>0&&Number.isInteger(q)?Math.round(Number(row.dataset.price)*100)*q*n/100:0;
  status.textContent=error||message;status.classList.toggle('warning',Boolean(error)||Boolean(row&&a&&b&&n>0&&Array.from(dayMaps.get(row.dataset.room).keys()).filter(d=>d>=a&&d<b).length<n));status.classList.toggle('is-awaiting',Boolean(a&&!b&&!error));
  submit.disabled=!valid;beds.max=row?row.dataset.capacity:'';
  departure.min=a?iso(utc(a)+86400000):today;
  $('sd140-summary-room').textContent=row?row.dataset.name:t('Choose a room');$('sd140-summary-dates').textContent=a&&b?fmt(a)+' – '+fmt(b):a?t('Arrival: %(date)s · choose departure',{date:fmt(a)}):t('Select arrival and departure');$('sd140-summary-beds').textContent=(Number.isInteger(q)?q:0)+' '+t(q===1?'guest':'guests')+' · '+(n>0?n+' '+t(n===1?'night':'nights'):t('select dates'));
  $('sd146-price-detail').textContent=row&&n>0?q+' '+t(q===1?'bed':'beds')+' × '+money(Number(row.dataset.price))+' × '+n+' '+t(n===1?'night':'nights'):'';$('sd140-total').textContent=valid?money(total):'—';
  $('sd146-mobile-summary').hidden=!valid;$('sd146-mobile-text').textContent=(row?.dataset.name||'')+' · '+money(total);
  cells.forEach(c=>{const same=c.closest('.sd142-roomrow').dataset.room===room.value,d=c.dataset.day,start=Boolean(same&&a===d),end=Boolean(same&&b===d),selected=Boolean(same&&a&&b&&d>=a&&d<b);c.classList.toggle('is-selected',selected);c.classList.toggle('is-start',start);c.classList.toggle('is-end',end);c.querySelector('.sd146-boundary').textContent=start?t('Arrival'):end?t('Departure'):'';c.querySelector('.sd140-pick').setAttribute('aria-pressed',String(start||end||selected));});
  syncTabstop();alternatives(a,b,q,Boolean(error));return valid;
 }
 function preview(entry,row,trigger){
  previewTrigger=trigger;$('sd146-preview-status').textContent=entry.status==='pending'?t('Pending request'):t('Confirmed reservation');$('sd146-preview-guest').textContent=entry.guest;$('sd146-preview-room').textContent=row.dataset.name;$('sd146-preview-arrival').textContent=fmt(entry.arrival);$('sd146-preview-departure').textContent=fmt(entry.departure);$('sd146-preview-beds').textContent=entry.beds;$('sd146-preview-link').href=entry.href;
  if(typeof $('sd146-preview').showModal==='function')$('sd146-preview').showModal();else window.location.assign(entry.href);
 }
 function renderBars(){
  rows.forEach(row=>{
   const layer=row.querySelector('.sd142-bars');layer.replaceChildren();const visible=Array.from(row.querySelectorAll('.sd142-day')).filter(c=>!c.hidden),segments=[];
   (entries.get(row.dataset.room)||[]).forEach(e=>{const occupied=visible.map((c,i)=>c.dataset.day>=e.arrival&&c.dataset.day<e.departure?i:-1).filter(i=>i>=0);if(occupied.length)segments.push({...e,start:occupied[0],end:occupied.at(-1)+1});});
   segments.sort((a,b)=>a.start-b.start||b.end-a.end);const lanes=[];
   segments.forEach(e=>{let lane=lanes.findIndex(end=>end<=e.start);if(lane<0){lane=lanes.length;lanes.push(e.end);}else lanes[lane]=e.end;
    const wrapper=document.createElement('div');wrapper.className='sd146-booking-wrap'+(e.status==='pending'?' pending':'');wrapper.style.gridColumn=(e.start+1)+' / span '+(e.end-e.start);wrapper.style.gridRow=String(lane+1);
    const link=document.createElement('a');link.className='sd142-booking';link.href=e.href;link.textContent=(e.status==='pending'?t('Pending'):t('Confirmed'))+' · '+e.guest+' · '+e.beds+' '+t(Number(e.beds)===1?'bed':'beds');link.title=link.textContent+' · '+fmt(e.arrival)+' – '+fmt(e.departure);
    const button=document.createElement('button');button.type='button';button.className='sd146-booking-preview';button.textContent='ⓘ';button.setAttribute('aria-label',t('Preview %(guest)s reservation',{guest:e.guest}));button.addEventListener('click',()=>preview(e,row,button));wrapper.append(link,button);layer.append(wrapper);
   });row.style.setProperty('--sd142-lanes',Math.max(1,lanes.length));
  });
 }
 function renderWindow(){
  const total=heads.length,count=$('sd146-window').value==='all'?total:Number($('sd146-window').value);windowCount=count;offset=Math.max(0,Math.min(offset,total-count));
  board.style.setProperty('--sd142-days',Math.min(count,total));heads.forEach((h,i)=>{h.hidden=i<offset||i>=offset+count;});
  rows.forEach(r=>{r.hidden=Boolean($('sd146-room-filter').value&&$('sd146-room-filter').value!==r.dataset.room);board.querySelector('[data-room-label="'+r.dataset.room+'"]').hidden=r.hidden;Array.from(r.querySelectorAll('.sd142-day')).forEach((c,i)=>{c.hidden=i<offset||i>=offset+count;});});
  $('sd146-prev').disabled=offset<=0;$('sd146-next').disabled=offset+count>=total;$('sd146-window-label').textContent=total?fmt(heads[offset].dataset.day)+' – '+fmt(heads[Math.min(total-1,offset+count-1)].dataset.day):t('No dates');renderBars();syncTabstop();scroll.scrollLeft=0;
 }
 function showSelection(){const index=heads.findIndex(h=>h.dataset.day===arrival.value);if(index>=0&&(index<offset||index>=offset+windowCount)){offset=index;renderWindow();}if($('sd146-room-filter').value&&$('sd146-room-filter').value!==room.value){$('sd146-room-filter').value='';renderWindow();}}
 board.addEventListener('click',e=>{const button=e.target.closest('.sd140-pick');if(!button||button.disabled)return;const cell=button.closest('.sd142-day'),row=cell.closest('.sd142-roomrow'),day=cell.dataset.day;
  if(day>root.dataset.latestArrival&&(!awaitingEnd||room.value!==row.dataset.room))return;
  if(awaitingEnd&&room.value===row.dataset.room&&day>arrival.value){departure.value=day;awaitingEnd=false;}
  else{if(Number(cell.dataset.free)<1)return;room.value=row.dataset.room;arrival.value=day;departure.value='';awaitingEnd=true;}validate();
 });
 // One calendar date in the Tab order; arrow keys explore without booking.
 function syncTabstop(preferred){
  const all=cells.map(c=>c.querySelector('.sd140-pick'));
  const visible=all.filter(b=>!b.disabled&&!b.closest('.sd142-day').hidden&&!b.closest('.sd142-roomrow').hidden);
  const target=visible.includes(preferred)?preferred:visible.includes(document.activeElement)?document.activeElement:visible.find(b=>b.getAttribute('aria-pressed')==='true')||visible[0];
  all.forEach(b=>b.tabIndex=b===target?0:-1);
 }
 board.addEventListener('focusin',e=>{if(e.target.matches('.sd140-pick'))syncTabstop(e.target);});
 board.addEventListener('keydown',e=>{
  const button=e.target.closest('.sd140-pick');if(!button||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End','PageUp','PageDown'].includes(e.key))return;
  e.preventDefault();const cell=button.closest('.sd142-day'),row=cell.closest('.sd142-roomrow');let next;
  const all=Array.from(row.querySelectorAll('.sd142-day')).filter(c=>!c.querySelector('.sd140-pick').disabled),index=all.indexOf(cell),visible=all.filter(c=>!c.hidden);
  if(e.key==='Home')next=visible[0];else if(e.key==='End')next=visible.at(-1);
  else if(['ArrowLeft','ArrowRight','PageUp','PageDown'].includes(e.key))next=all[index+({'ArrowLeft':-1,'ArrowRight':1,'PageUp':-windowCount,'PageDown':windowCount}[e.key])];
  else{const activeRows=rows.filter(r=>!r.hidden),direction=e.key==='ArrowUp'?-1:1;for(let i=activeRows.indexOf(row)+direction;i>=0&&i<activeRows.length;i+=direction){const candidate=activeRows[i].querySelector('[data-day="'+cell.dataset.day+'"]');if(candidate&&!candidate.querySelector('.sd140-pick').disabled){next=candidate;break;}}}
  if(!next)return;
  const dayIndex=heads.findIndex(h=>h.dataset.day===next.dataset.day);
  if(dayIndex<offset||dayIndex>=offset+windowCount){offset=dayIndex<offset?Math.max(0,dayIndex-windowCount+1):dayIndex;renderWindow();}
  const target=next.querySelector('.sd140-pick');syncTabstop(target);target.focus();target.scrollIntoView({block:'nearest',inline:'nearest'});
 });
 [room,arrival,departure,beds].forEach(el=>el.addEventListener('change',()=>{awaitingEnd=Boolean(arrival.value&&!departure.value);showSelection();validate();}));beds.addEventListener('input',validate);
 $('sd146-reset').addEventListener('click',()=>{room.value='';arrival.value='';departure.value='';beds.value='1';awaitingEnd=false;validate();status.textContent=t('Stay selection reset. Your guest details are kept.');arrival.focus();});
 $('sd146-window').addEventListener('change',renderWindow);$('sd146-room-filter').addEventListener('change',renderWindow);$('sd146-prev').addEventListener('click',()=>{offset-=windowCount;renderWindow();});$('sd146-next').addEventListener('click',()=>{offset+=windowCount;renderWindow();});
 $('sd146-preview-close').addEventListener('click',()=>$('sd146-preview').close());$('sd146-preview').addEventListener('close',()=>(previewTrigger?.isConnected?previewTrigger:$('sd146-window')).focus());
 form.addEventListener('submit',e=>{if(!validate()){e.preventDefault();status.focus();}else{submit.disabled=true;submit.textContent=t('Saving reservation…');}});
 $('sd146-window').value=window.matchMedia('(max-width:850px)').matches?'7':'14';const initial=heads.findIndex(h=>h.dataset.day===(arrival.value||today));offset=Math.max(0,initial);renderWindow();validate();root.querySelector('.sd140-errors')?.focus();
})();
