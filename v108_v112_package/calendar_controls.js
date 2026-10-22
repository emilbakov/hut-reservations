
/* Additional calendar controls; uses server-rendered statuses, never infers availability. */
(function(){
'use strict';
function setup(){
var grid=document.querySelector('.sd-calendar-grid');
if(!grid||grid.dataset.sdFiltersReady)return;
var section=grid.closest('section.panel');
if(!section)return;
var table=grid.querySelector('table'),tbody=table&&table.tBodies[0];
if(!tbody)return;
var rows=Array.from(tbody.rows).filter(function(r){return r.querySelector('.sd-room-select')});
if(!rows.length)return;
grid.dataset.sdFiltersReady='1';
var toolbar=document.createElement('div');toolbar.className='sd-cal-filterbar';
function field(labelText,control){
 var label=document.createElement('label');label.textContent=labelText;label.append(control);toolbar.append(label);return control;
}
var search=document.createElement('input');search.type='search';search.placeholder='Search rooms';search.autocomplete='off';
search.setAttribute('aria-label','Search rooms by name');field('Find a room',search);
var status=document.createElement('select');status.setAttribute('aria-label','Filter rooms by availability status');
[['all','All rooms'],['available','Has available nights'],['limited','Has limited nights'],['full','Has full nights'],['closed','Has closed nights'],['over','Has over-capacity nights']].forEach(function(o){
 var option=document.createElement('option');option.value=o[0];option.textContent=o[1];status.append(option);
});field('Show rooms',status);
var compact=document.createElement('button');compact.type='button';compact.textContent='Compact view';compact.setAttribute('aria-pressed','false');compact.setAttribute('aria-label','Toggle compact calendar rows');
toolbar.append(compact);
var clear=document.createElement('button');clear.type='button';clear.textContent='Clear filters';toolbar.append(clear);
var count=document.createElement('span');count.className='sd-cal-results';count.setAttribute('role','status');count.setAttribute('aria-live','polite');toolbar.append(count);
var empty=document.createElement('div');empty.className='sd-cal-empty';empty.hidden=true;empty.textContent='No rooms match these filters. Clear filters to show all rooms.';
section.insertBefore(toolbar,grid);grid.after(empty);
function apply(){
 var q=search.value.trim().toLocaleLowerCase(),s=status.value,n=0;
 rows.forEach(function(row){
  var name=row.querySelector('.sd-room-select').textContent.toLocaleLowerCase();
  var matches=!q||name.includes(q);
  if(s!=='all')matches=matches&&!!row.querySelector('.sd-day-cell.'+s);
  row.hidden=!matches;if(matches)n++;
 });
 count.textContent=n+' of '+rows.length+' rooms shown';
 empty.hidden=n!==0;
}
search.addEventListener('input',apply);status.addEventListener('change',apply);
compact.addEventListener('click',function(){
 var enabled=grid.classList.toggle('sd-compact');
 compact.setAttribute('aria-pressed',String(enabled));
 compact.textContent=enabled?'Comfortable view':'Compact view';
});
clear.addEventListener('click',function(){search.value='';status.value='all';apply();search.focus()});
/* Direct navigation to the selected room, without changing existing detail behavior. */
rows.forEach(function(row){
 var btn=row.querySelector('.sd-room-select');
 if(btn){btn.title='Show numbered bed details for '+btn.firstChild.textContent.trim();}
});
apply();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});
else setup();
})();
