(function () {
  'use strict';
  const sidebar = document.getElementById('sd116-sidebar');
  const open = document.getElementById('sd116-open');
  const close = document.getElementById('sd116-close');
  const backdrop = document.getElementById('sd116-backdrop');
  if (!sidebar || !open || !close || !backdrop) return;
  let previousFocus = null;
  function toggle(show) {
    document.body.classList.toggle('sd116-menu-open', show);
    backdrop.hidden = !show;
    open.setAttribute('aria-expanded', show ? 'true' : 'false');
    if (show) { previousFocus = document.activeElement; close.focus(); }
    else if (previousFocus && previousFocus.isConnected) { previousFocus.focus(); }
  }
  open.addEventListener('click', function () { toggle(true); });
  close.addEventListener('click', function () { toggle(false); });
  backdrop.addEventListener('click', function () { toggle(false); });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && document.body.classList.contains('sd116-menu-open')) toggle(false);
  });
  sidebar.addEventListener('click', function (event) {
    if (event.target.closest('a') && document.body.classList.contains('sd116-menu-open')) toggle(false);
  });
  const property = document.getElementById('sd116-property-select');
  if (property) property.addEventListener('change', function () {
    if (property.value) window.location.assign(property.value);
  });
})();
