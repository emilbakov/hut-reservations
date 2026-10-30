/* No autoplay. Photos remain swipeable without JavaScript. Reinitialize after availability refresh. */
(()=>{'use strict';
 function init(root){
  root.querySelectorAll('.room188-gallery').forEach(gallery=>{
   if(gallery.dataset.ready)return;
   const track=gallery.querySelector('.room188-track'),slides=Array.from(track.children),buttons=Array.from(gallery.querySelectorAll('[data-gallery-index]')),prev=gallery.querySelector('[data-gallery-prev]'),next=gallery.querySelector('[data-gallery-next]'),count=gallery.querySelector('.room188-count');
   gallery.dataset.ready='true';if(slides.length<2)return;
   const index=()=>Math.max(0,Math.min(slides.length-1,Math.round(track.scrollLeft/(track.clientWidth||1))));
   function update(){const i=index();prev.disabled=i===0;next.disabled=i===slides.length-1;count.textContent=(i+1)+' / '+slides.length;buttons.forEach((button,n)=>button.setAttribute('aria-pressed',String(n===i)));}
   function show(i){i=Math.max(0,Math.min(slides.length-1,i));track.scrollTo({left:i*track.clientWidth,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}
   buttons.forEach(button=>button.addEventListener('click',()=>show(Number(button.dataset.galleryIndex))));prev.addEventListener('click',()=>show(index()-1));next.addEventListener('click',()=>show(index()+1));
   track.addEventListener('scroll',update,{passive:true});track.addEventListener('keydown',event=>{if(event.key==='ArrowRight'||event.key==='ArrowLeft'){event.preventDefault();show(index()+(event.key==='ArrowRight'?1:-1));}});
   gallery.querySelectorAll('.room188-controls,.room188-thumbs').forEach(node=>node.hidden=false);update();
  });
 }
 document.addEventListener('DOMContentLoaded',()=>{init(document);const list=document.getElementById('ph-room-list');if(list)new MutationObserver(()=>init(list)).observe(list,{childList:true,subtree:true});});
})();
