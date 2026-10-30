(() => {
  'use strict';
  const tablist = document.querySelector('[data-tabs]');
  if (tablist) {
    const tabs = Array.from(tablist.querySelectorAll('[data-tab]'));
    const panels = Array.from(document.querySelectorAll('[data-tab-panel]'));
    function selectTab(tab, focus) {
      tabs.forEach(button => {
        const active = button === tab;
        button.setAttribute('aria-selected', String(active));
        button.tabIndex = active ? 0 : -1;
      });
      panels.forEach(panel => { panel.hidden = panel.dataset.tabPanel !== tab.dataset.tab; });
      if (focus) tab.focus();
    }
    tablist.hidden = false;
    document.querySelector('.h168-time-photos').dataset.enhanced = 'true';
    selectTab(tabs.find(tab => tab.dataset.tab === 'now') || tabs[0], false);
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => selectTab(tab, false));
      tab.addEventListener('keydown', event => {
        let target;
        if (event.key === 'ArrowRight') target = tabs[(index + 1) % tabs.length];
        if (event.key === 'ArrowLeft') target = tabs[(index + tabs.length - 1) % tabs.length];
        if (event.key === 'Home') target = tabs[0];
        if (event.key === 'End') target = tabs[tabs.length - 1];
        if (target) { event.preventDefault(); selectTab(target, true); }
      });
    });
  }
  const menu = document.querySelector('.h168-menu');
  if (menu) {
    menu.querySelectorAll('nav a').forEach(link => link.addEventListener('click', () => { menu.open = false; }));
    menu.addEventListener('keydown', event => {
      if (event.key === 'Escape') { menu.open = false; menu.querySelector('summary').focus(); }
    });
  }
  const dialog = document.querySelector('.h168-lightbox');
  const photos = Array.from(document.querySelectorAll('a[data-photo]'));
  if (!dialog || typeof dialog.showModal !== 'function' || !photos.length) return;
  const large = dialog.querySelector('img');
  const title = dialog.querySelector('#h168-lightbox-title');
  const count = dialog.querySelector('[role="status"]');
  const close = dialog.querySelector('.h168-lightbox-close');
  let current = 0;
  let opener;
  function showPhoto(index) {
    current = (index + photos.length) % photos.length;
    const photo = photos[current];
    large.src = photo.href;
    large.alt = photo.querySelector('img').alt;
    title.textContent = photo.dataset.photoTitle || large.alt;
    count.textContent = `${current + 1} / ${photos.length}`;
  }
  photos.forEach((photo, index) => photo.addEventListener('click', event => {
    event.preventDefault();
    opener = photo;
    showPhoto(index);
    dialog.showModal();
    document.documentElement.classList.add('h168-lightbox-open');
    close.focus();
  }));
  close.addEventListener('click', () => dialog.close());
  dialog.querySelectorAll('[data-photo-direction]').forEach(button => button.addEventListener('click', () => showPhoto(current + Number(button.dataset.photoDirection))));
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault(); showPhoto(current + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('close', () => {
    document.documentElement.classList.remove('h168-lightbox-open');
    if (opener && opener.isConnected) opener.focus();
  });
})();
