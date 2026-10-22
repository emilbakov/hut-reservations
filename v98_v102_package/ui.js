/* Progressive enhancement. Without JavaScript the original full page stays usable. */
(function(){
'use strict';
var main=document.querySelector('main');if(!main)return;
var panels=Array.from(main.querySelectorAll('section.panel'));
var categories=[
 {id:'overview',label:'Overview',match:/operations overview|attention overview|seven.day operations window|operations summary/i},
 {id:'reservations',label:'Reservations',match:/conflict|critical issues|manager action|daily operations checklist/i},
 {id:'availability',label:'Availability',match:/availability|numbered bed|bed details/i},
 {id:'housekeeping',label:'Housekeeping',match:/arrival|readiness|cleaning/i},
 {id:'reports',label:'Reports',match:/export|report|print/i}
];
var categoryMap=new Map();categories.forEach(function(c){categoryMap.set(c.id,[])});
var uncategorized=[];
panels.forEach(function(panel){
 var heading=panel.querySelector('h2');var title=heading?heading.textContent.trim():'';
 var category=categories.find(function(c){return c.match.test(title)});
 if(category){categoryMap.get(category.id).push(panel);panel.dataset.sdCategory=category.id}
 else{uncategorized.push(panel);panel.dataset.sdCategory='overview';categoryMap.get('overview').push(panel)}
 panel.classList.add('sd-view');
});
// Keep the four KPI cards in Overview. Preserve all existing forms, anchors and IDs.
var kpis=main.querySelector('section.cards');if(kpis){kpis.dataset.sdCategory='overview';kpis.classList.add('sd-view')}
var hero=main.querySelector('.hero');
var sidebar=document.createElement('aside');sidebar.className='sd-sidebar';sidebar.setAttribute('aria-label','Manager navigation');
var brand=document.createElement('div');brand.className='sd-brand';
var mark=document.createElement('span');mark.className='sd-brand-mark';mark.textContent='▲';
var brandText=document.createElement('span');brandText.textContent='SummitDesk';brand.append(mark,brandText);sidebar.append(brand);
var nav=document.createElement('nav');nav.setAttribute('aria-label','Workspaces');sidebar.append(nav);
var buttons=[];
function button(label,id){var a=document.createElement('a');a.href='#'+id;a.className='sd-side-link';a.textContent=label;a.dataset.sdTab=id;nav.append(a);buttons.push(a);return a}
categories.forEach(function(c){button(c.label,c.id)});
var bottom=document.createElement('div');bottom.className='sd-sidebar-bottom';
var back=hero&&hero.querySelector('a[href]');if(back){var b=document.createElement('a');b.className='sd-side-link';b.href=back.href;b.textContent='← Staff Hub';bottom.append(b)}sidebar.append(bottom);
var mobile=document.createElement('div');mobile.className='sd-mobile-top';
var menu=document.createElement('button');menu.type='button';menu.setAttribute('aria-label','Open navigation');menu.setAttribute('aria-expanded','false');menu.textContent='☰';
var mobileBrand=document.createElement('strong');mobileBrand.textContent='SummitDesk';mobile.append(menu,mobileBrand);
var shade=document.createElement('button');shade.type='button';shade.className='sd-mobile-shade';shade.setAttribute('aria-label','Close navigation');
document.body.insertBefore(sidebar,document.body.firstChild);main.insertBefore(mobile,main.firstChild);document.body.append(shade);
var intro=document.createElement('p');intro.className='sd-intro';intro.textContent='Everything you need for daily hut operations, organized by workspace.';
if(hero)hero.insertAdjacentElement('afterend',intro);
var actions=document.createElement('div');actions.className='sd-overview-actions';
['Reservations','Availability','Housekeeping','Reports'].forEach(function(label){var b=document.createElement('button');b.type='button';b.textContent='Open '+label;b.addEventListener('click',function(){location.hash=label.toLowerCase()});actions.append(b)});
if(kpis)kpis.insertAdjacentElement('afterend',actions);
function show(tab,keepHash){if(!categoryMap.has(tab))tab='overview';
 main.querySelectorAll('.sd-view').forEach(function(el){el.hidden=el.dataset.sdCategory!==tab});
 if(actions)actions.hidden=tab!=='overview';
 buttons.forEach(function(a){if(a.dataset.sdTab===tab)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
 document.body.classList.remove('sd-menu-open');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','Open navigation');
 if(!keepHash&&location.hash!=='#'+tab)history.replaceState(null,'','#'+tab);
 window.scrollTo({top:0,behavior:'instant'});
}
function current(){var hash=decodeURIComponent(location.hash.slice(1));
 if(categoryMap.has(hash))return hash;
 if(hash){var el=document.getElementById(hash);if(el){var section=el.closest('section.panel');if(section&&section.dataset.sdCategory)return section.dataset.sdCategory}}
 return 'overview'}
function sync(){show(current(),true);var id=decodeURIComponent(location.hash.slice(1));if(!categoryMap.has(id)){var target=document.getElementById(id);if(target)target.scrollIntoView()}}
window.addEventListener('hashchange',sync);
menu.addEventListener('click',function(){var open=document.body.classList.toggle('sd-menu-open');menu.setAttribute('aria-expanded',String(open));menu.setAttribute('aria-label',open?'Close navigation':'Open navigation')});
shade.addEventListener('click',function(){document.body.classList.remove('sd-menu-open');menu.setAttribute('aria-expanded','false')});
document.addEventListener('keydown',function(e){if(e.key==='Escape'){document.body.classList.remove('sd-menu-open');menu.setAttribute('aria-expanded','false')}});
// Original quick-jump links keep working by revealing their target section.
Array.from(main.querySelectorAll('a[href^="#"]')).forEach(function(a){a.addEventListener('click',function(){var target=document.getElementById(a.hash.slice(1));if(target){var section=target.closest('section.panel');if(section&&section.dataset.sdCategory)show(section.dataset.sdCategory,true)}})});
document.body.classList.add('sd-ready');sync();
})();
