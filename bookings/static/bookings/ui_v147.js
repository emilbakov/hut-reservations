/* Django supplies translated text as inert JSON; guest content is never HTML. */
(()=>{'use strict';
 const el=document.getElementById('sd147-i18n');
 const messages=el?JSON.parse(el.textContent):{};
 const locale=document.documentElement.lang||'en';
 function text(source,values={}){
  return (messages[source]||source).replace(/%\((\w+)\)s/g,(match,key)=>Object.hasOwn(values,key)?String(values[key]):match);
 }
 const amount=value=>new Intl.NumberFormat(locale,{useGrouping:false,minimumFractionDigits:2,maximumFractionDigits:2}).format(value);
 const date=value=>value?new Date(value+'T00:00:00Z').toLocaleDateString(locale,{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}):'';
 window.SummitDeskUI={text,amount,date,locale};
})();
