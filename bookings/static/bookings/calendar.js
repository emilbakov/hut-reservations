document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('availability-calendar');
  if (!root) return;
  const title = document.getElementById('cal-title');
  const arrival = document.querySelector('input[name="check_in"]');
  const departure = document.querySelector('input[name="check_out"]');
  const today = new Date();
  let cursor = new Date(today.getFullYear(), today.getMonth(), 1);
  const weekday = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const iso = (y,m,d) => `${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
  async function render() {
    const y = cursor.getFullYear(), m = cursor.getMonth();
    title.textContent = cursor.toLocaleDateString(undefined,{month:'long',year:'numeric'});
    root.replaceChildren();
    weekday.forEach(w => { const label=document.createElement('span');label.className='cal-weekday';label.textContent=w;root.append(label); });
    const offset=(new Date(y,m,1).getDay()+6)%7;
    for(let i=0;i<offset;i++) root.append(document.createElement('span'));
    try {
      const response=await fetch(`${root.dataset.endpoint}?year=${y}&month=${m}`,{credentials:'same-origin'});
      if (!response.ok) throw new Error('Outside booking window');
      const data=await response.json();
      const byDate=new Map(data.days.map(d=>[d.date,d]));
      const count=new Date(y,m+1,0).getDate();
      for(let d=1;d<=count;d++) {
        const key=iso(y,m,d), info=byDate.get(key), button=document.createElement('button');
        button.type='button';button.className='cal-day '+(!info?'cal-disabled':info.free_beds?'cal-free':'cal-full');
        button.disabled=!info||!info.free_beds;
        button.textContent=String(d);
        button.title=info?`${info.free_beds} beds free`:'Not available';
        button.setAttribute('aria-label',`${key}: ${info?info.free_beds+' beds free':'not bookable'}`);
        if(!button.disabled) button.addEventListener('click',()=>{
          if(arrival) arrival.value=key;
          if(departure && (!departure.value || departure.value<=key)) {
            const next=new Date(y,m,d+1);departure.value=iso(next.getFullYear(),next.getMonth(),next.getDate());
          }
          arrival?.focus();
        });
        root.append(button);
      }
    } catch(e) { const note=document.createElement('p');note.textContent='Calendar unavailable for this month.';root.append(note); }
  }
  document.getElementById('cal-prev').addEventListener('click',()=>{cursor=new Date(cursor.getFullYear(),cursor.getMonth()-1,1);render();});
  document.getElementById('cal-next').addEventListener('click',()=>{cursor=new Date(cursor.getFullYear(),cursor.getMonth()+1,1);render();});
  render();
});