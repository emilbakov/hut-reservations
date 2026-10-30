(()=>{'use strict';document.addEventListener('DOMContentLoaded',()=>{
 const add=document.getElementById('room188-add-photo'),empty=document.getElementById('room188-empty-form'),container=document.getElementById('room188-photo-forms'),total=document.getElementById('id_gallery-TOTAL_FORMS');
 if(!add||!empty||!container||!total)return;add.hidden=false;
 add.addEventListener('click',()=>{const index=Number(total.value);if(!Number.isInteger(index)||index<0||index>=1000)return;const wrapper=document.createElement('div');wrapper.innerHTML=empty.innerHTML.replace(/__prefix__/g,String(index));const row=wrapper.firstElementChild;container.append(row);total.value=String(index+1);row.querySelector('input[type=file]')?.focus();});
});})();
