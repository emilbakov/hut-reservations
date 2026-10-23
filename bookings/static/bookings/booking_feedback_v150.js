/* Server-rendered errors remain visible with JS disabled via the form anchor. */
document.addEventListener('DOMContentLoaded',()=>{
 const summary=document.getElementById('sd150-errors');
 if(!summary)return;
 function reveal(){summary.focus({preventScroll:true});summary.scrollIntoView({block:'start',behavior:'auto'});}
 if(!summary.hidden){reveal();requestAnimationFrame(reveal);}
 summary.addEventListener('click',event=>{
  const link=event.target.closest('a[href^="#"]');if(!link)return;
  const field=document.getElementById(link.hash.slice(1));if(!field)return;
  event.preventDefault();if(!field.matches('input,textarea,select,button,a'))field.tabIndex=-1;
  field.focus({preventScroll:true});field.scrollIntoView({block:'center',behavior:'auto'});
 });
});
