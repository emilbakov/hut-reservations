
/* Accessible progressive enhancement; never recalculates reservation availability. */
(function(){
'use strict';
var panel=Array.from(document.querySelectorAll('main section.panel')).find(function(s){
 var h=s.querySelector('h2');return h&&/room availability calendar/i.test(h.textContent);
});
if(!panel||panel.dataset.sdCalendarEnhanced)return;
var original=panel.querySelector('.scroll table');
if(!original||!original.tHead||!original.tBodies.length)return;
var body=original.tBodies[0],rows=Array.from(body.rows).filter(function(r){return r.cells.length===8});
if(!rows.length)return;
panel.dataset.sdCalendarEnhanced='1';
panel.id=panel.id||'room-availability';
var dayLabels=Array.from(original.tHead.rows[0].cells).slice(1).map(function(c){return c.textContent.trim()});
var selected=null;
var dateInput=document.querySelector('input[name="forecast_start"]');
var start=dateInput&&/^\d{4}-\d{2}-\d{2}$/.test(dateInput.value)?dateInput.value:null;
var today=dateInput&&dateInput.min||null,max=dateInput&&dateInput.max||null;
function parseDay(s){var p=s.split('-').map(Number);return new Date(Date.UTC(p[0],p[1]-1,p[2]))}
function iso(d){return d.toISOString().slice(0,10)}
function shift(s,n){var d=parseDay(s);d.setUTCDate(d.getUTCDate()+n);return iso(d)}
function urlFor(s){var u=new URL(location.href);u.searchParams.set('operations','1');u.searchParams.set('forecast_start',s);u.hash='availability';return u.toString()}
var toolbar=document.createElement('div');toolbar.className='sd-calendar-tools';
var range=document.createElement('div');range.className='sd-calendar-range';
range.textContent=start?start+' — '+shift(start,6):'Selected seven-day window';
var nav=document.createElement('nav');nav.className='sd-calendar-nav';nav.setAttribute('aria-label','Availability dates');
function link(label,delta){
 var a=document.createElement('a');a.textContent=label;a.href=start?urlFor(shift(start,delta)):'#availability';
 var target=start?shift(start,delta):null;
 if(!target||(delta<0&&today&&target<today)||(delta>0&&max&&target>max)){
 a.setAttribute('aria-disabled','true');a.setAttribute('tabindex','-1');a.removeAttribute('href');
 }
 return a;
}
nav.append(link('← Previous week',-7));
var current=document.createElement('span');current.className='sd-calendar-range';current.textContent=range.textContent;nav.append(current);
nav.append(link('Next week →',7));
toolbar.append(nav);
var legend=document.createElement('div');legend.className='sd-calendar-legend';legend.setAttribute('aria-label','Availability legend');
[['available','Available'],['limited','Limited'],['full','Full'],['over','Over capacity'],['closed','Closed']].forEach(function(item){
 var entry=document.createElement('span'),dot=document.createElement('i');dot.className='sd-calendar-dot';dot.dataset.status=item[0];dot.setAttribute('aria-hidden','true');entry.append(dot,document.createTextNode(item[1]));legend.append(entry);
});
var table=original.cloneNode(false),thead=original.tHead.cloneNode(true),tbody=document.createElement('tbody');
table.append(thead,tbody);
var all=[];
rows.forEach(function(row){
 var cells=Array.from(row.cells),name=cells[0].childNodes[0]?cells[0].childNodes[0].textContent.trim():cells[0].textContent.trim();
 var bedText=cells[0].querySelector('.muted');var bedInfo=bedText?bedText.textContent.trim():'';
 var tr=document.createElement('tr'),th=document.createElement('th'),button=document.createElement('button');
 button.type='button';button.className='sd-room-select';button.textContent=name;
 var small=document.createElement('small');small.textContent=bedInfo;button.append(small);
 button.setAttribute('aria-pressed','false');
 button.addEventListener('click',function(){selectRoom(name,button)});
 th.append(button);tr.append(th);
 cells.slice(1).forEach(function(c){
 var td=document.createElement('td'),box=document.createElement('div');
 var status=['over','closed','full','limited','available'].find(function(s){return c.classList.contains(s)})||'available';
 box.className='sd-day-cell '+status;
 var strong=document.createElement('strong'),minor=document.createElement('small');
 var m=c.textContent.match(/(-?\d+)\s+free/i);
 var free=m?Number(m[1]):null;
 strong.textContent=status==='closed'?'Closed':status==='over'?'Over capacity':status==='full'?'Full':free===null?'Check':'Free: '+free;
 minor.textContent=(c.textContent.match(/(\d+)\s+confirmed/i)||[])[1]||'0';
 minor.textContent+=' confirmed';
 box.append(strong,minor);box.title=c.textContent.replace(/\s+/g,' ').trim();
 box.setAttribute('aria-label',(dayLabels[Array.from(tr.cells).length-1]||'Day')+': '+box.title);
 td.append(box);tr.append(td);
 });
 tbody.append(tr);all.push({name:name,button:button});
});
var wrap=document.createElement('div');wrap.className='sd-calendar-grid';wrap.setAttribute('role','region');
wrap.setAttribute('aria-label','Room availability, horizontally scrollable');wrap.tabIndex=0;wrap.append(table);
var details=document.createElement('section');details.className='sd-room-details';details.hidden=true;
details.setAttribute('aria-live','polite');
function selectRoom(name,button){
 selected=name;
 all.forEach(function(r){r.button.setAttribute('aria-pressed',String(r.button===button))});
 details.replaceChildren();
 var heading=document.createElement('h3');heading.textContent=name+' · Numbered beds';details.append(heading);
 var note=document.createElement('p');note.className='sd-calendar-note';
 note.textContent='Assigned, held, closed and conflicting beds reflect recorded assignments. Unassigned does not mean guaranteed available.';
 details.append(note);
 var bedSection=document.getElementById('bed-details');
 var source=bedSection&&bedSection.querySelector('table');
 if(source){
 var copy=source.cloneNode(true);
 Array.from(copy.tBodies[0].rows).forEach(function(r){
 var title=r.cells[0]?r.cells[0].textContent.trim():'';
 if(!title.startsWith(name+' / '))r.remove();
 });
 if(copy.tBodies[0].rows.length){
 var holder=document.createElement('div');holder.className='scroll';holder.append(copy);details.append(holder);
 }else{
 var p=document.createElement('p');p.textContent='No numbered beds recorded for this room.';details.append(p);
 }
 }else{
 var p=document.createElement('p');p.textContent='Open Numbered Bed Details for individual assignments.';details.append(p);
 }
 details.hidden=false;
}
var note=document.createElement('p');note.className='sd-calendar-note';
note.textContent='Room counts are planning estimates, not confirmation that a particular numbered bed is free. Select a room to inspect recorded bed assignments. Dates represent occupied nights; check-out is excluded.';
var originalWrap=original.closest('.scroll');
panel.insertBefore(toolbar,originalWrap);
panel.insertBefore(legend,originalWrap);
originalWrap.replaceWith(wrap);
wrap.after(details,note);
if(all.length)selectRoom(all[0].name,all[0].button);
})();
