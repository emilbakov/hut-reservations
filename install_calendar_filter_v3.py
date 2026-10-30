#!/usr/bin/env python3
"""Patch the existing SummitDesk calendar without overwriting unrelated changes."""
from pathlib import Path
from datetime import datetime
import sys

root = Path(__file__).resolve().parent
html = root / 'floorplans/templates/floorplans/property_calendar_v138.html'
js = root / 'floorplans/static/floorplans/property_planner_v147.js'
css = root / 'floorplans/static/floorplans/property_available_filter_v3.css'
if not html.is_file() or not js.is_file():
    sys.exit('ERROR: Existing calendar files not found. No changes made.')
h, j = html.read_text(), js.read_text()
if 'id="sd148-available-only"' in h or 'function applyAvailabilityRoomFilter(){' in j:
    if 'id="sd148-available-only"' in h and 'function applyAvailabilityRoomFilter(){' in j:
        print('Filter already installed; nothing to change.')
        sys.exit(0)
    sys.exit('ERROR: Partial installation detected; no changes made.')

control = '''<label class="sd148-filter"><input type="checkbox" id="sd148-available-only" disabled> {% translate "Available rooms only" %}</label><span class="sd148-count" id="sd148-visible-count" role="status" aria-live="polite"></span>'''
html_anchor = '</select></label></div>\n   <p class="sd146-instructions"'
css_anchor = "<link rel=\"stylesheet\" href=\"{% static 'floorplans/property_availability_overview_v1.css' %}\">"
css_line = "<link rel=\"stylesheet\" href=\"{% static 'floorplans/property_available_filter_v3.css' %}\">"

new_func = ''' function applyAvailabilityRoomFilter(){
  const only=$('sd148-available-only'),count=$('sd148-visible-count');
  if(!only||!count)return;
  const a=arrival.value,b=departure.value,q=Number(beds.value);
  const ready=Boolean(a&&b&&Number.isInteger(q)&&q>=1&&daysBetween(a,b)>0);
  only.disabled=!ready;
  if(!ready)only.checked=false;
  let shown=0;
  rows.forEach(r=>{
   const chosen=$('sd146-room-filter').value;
   const match=(!chosen||chosen===r.dataset.room);
   // Keep the selected room visible so staff can correct an unavailable selection.
   const eligible=!only.checked||r.dataset.room===room.value||available(r,a,b,q);
   r.hidden=!(match&&eligible);
   board.querySelector('[data-room-label="'+r.dataset.room+'"]').hidden=r.hidden;
   if(!r.hidden)shown++;
  });
  count.textContent=shown+' / '+rows.length+' '+t('rooms shown');
 }
'''
old_rows = '''rows.forEach(r=>{r.hidden=Boolean($('sd146-room-filter').value&&$('sd146-room-filter').value!==r.dataset.room);board.querySelector('[data-room-label="'+r.dataset.room+'"]').hidden=r.hidden;Array.from(r.querySelectorAll('.sd142-day')).forEach((c,i)=>{c.hidden=i<offset||i>=offset+count;});});'''
new_rows = '''rows.forEach(r=>{Array.from(r.querySelectorAll('.sd142-day')).forEach((c,i)=>{c.hidden=i<offset||i>=offset+count;});});applyAvailabilityRoomFilter();'''
val_anchor = '  syncTabstop();alternatives(a,b,q,Boolean(error));return valid;'
val_replacement = '  applyAvailabilityRoomFilter();syncTabstop();alternatives(a,b,q,Boolean(error));return valid;'
listen_anchor = " $('sd146-window').addEventListener('change',renderWindow);"
listen_replacement = " $('sd148-available-only').addEventListener('change',()=>{applyAvailabilityRoomFilter();syncTabstop();});\n"+listen_anchor
checks=[(h,html_anchor,'HTML controls'),(h,css_anchor,'CSS link'),(j,' function renderWindow(){','JS window'),(j,old_rows,'JS room filtering'),(j,val_anchor,'JS validation'),(j,listen_anchor,'JS events')]
for haystack,needle,label in checks:
    if haystack.count(needle)!=1:
        sys.exit('ERROR: Unexpected '+label+' format; no changes made.')
h=h.replace(html_anchor,'</select></label>'+control+'</div>\n   <p class="sd146-instructions"',1)
h=h.replace(css_anchor,css_anchor+'\n'+css_line,1)
j=j.replace(' function renderWindow(){',new_func+' function renderWindow(){',1)
j=j.replace(old_rows,new_rows,1)
j=j.replace(val_anchor,val_replacement,1)
j=j.replace(listen_anchor,listen_replacement,1)
backup=root/('calendar_filter_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
backup.mkdir()
(backup/html.name).write_text(html.read_text())
(backup/js.name).write_text(js.read_text())
html.write_text(h)
js.write_text(j)
css.parent.mkdir(parents=True,exist_ok=True)
css.write_text('''.sd140 .sd148-filter{display:inline-flex;align-items:center;gap:8px;font-size:12px;font-weight:750;white-space:nowrap;cursor:pointer}
.sd140 .sd148-filter input{accent-color:#195b42;width:18px;height:18px;min-height:18px;margin:0}
.sd140 .sd148-filter:has(input:disabled){opacity:.6;cursor:not-allowed}
.sd140 .sd148-count{font-size:12px;color:#526d60;white-space:nowrap}
@media(max-width:850px){.sd140 .sd148-filter{min-height:40px}.sd140 .sd148-count{flex-basis:100%}}
''')
print('Filter installed. Backup:',backup)
