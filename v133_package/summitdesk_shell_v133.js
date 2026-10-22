(function () {
  'use strict';
  const sidebar = document.getElementById('sd116-sidebar');
  const open = document.getElementById('sd116-open');
  const close = document.getElementById('sd116-close');
  const backdrop = document.getElementById('sd116-backdrop');
  if (!sidebar || !open || !close || !backdrop) return;
  const mobile = window.matchMedia('(max-width: 900px)');
  let previousFocus = null;

  function toggle(show) {
    if (show && !mobile.matches) return;
    document.body.classList.toggle('sd116-menu-open', show);
    backdrop.hidden = !show;
    open.setAttribute('aria-expanded', show ? 'true' : 'false');
    // The hidden off-canvas navigation must not remain in the tab order.
    sidebar.inert = mobile.matches && !show;
    if (show) {
      previousFocus = document.activeElement;
      close.focus();
    } else if (previousFocus && previousFocus.isConnected) {
      previousFocus.focus();
    }
  }

  function syncBreakpoint() {
    if (!mobile.matches && document.body.classList.contains('sd116-menu-open')) {
      toggle(false);
    }
    sidebar.inert = mobile.matches && !document.body.classList.contains('sd116-menu-open');
  }

  open.addEventListener('click', function () { toggle(true); });
  close.addEventListener('click', function () { toggle(false); });
  backdrop.addEventListener('click', function () { toggle(false); });
  document.addEventListener('keydown', function (event) {
    if (!document.body.classList.contains('sd116-menu-open')) return;
    if (event.key === 'Escape') { toggle(false); return; }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(sidebar.querySelectorAll(
      'a[href], button:not([disabled]), select:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )).filter(function (element) { return element.getClientRects().length > 0; });
    if (!focusable.length) { event.preventDefault(); return; }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && (document.activeElement === first || !sidebar.contains(document.activeElement))) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && (document.activeElement === last || !sidebar.contains(document.activeElement))) {
      event.preventDefault(); first.focus();
    }
  });
  sidebar.addEventListener('click', function (event) {
    if (event.target.closest('a') && document.body.classList.contains('sd116-menu-open')) toggle(false);
  });
  if (mobile.addEventListener) mobile.addEventListener('change', syncBreakpoint);
  else if (mobile.addListener) mobile.addListener(syncBreakpoint);
  syncBreakpoint();

  const property = document.getElementById('sd116-property-select');
  if (property) property.addEventListener('change', function () {
    if (property.value) window.location.assign(property.value);
  });
})();
