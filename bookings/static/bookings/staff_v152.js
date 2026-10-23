/* Progressive enhancement: every filter and decision works without JavaScript. */
(() => {
  'use strict';
  document.documentElement.classList.add('sd152-js');
  document.querySelectorAll('form[data-sd152-auto]').forEach(form => {
    form.addEventListener('change', event => {
      if (!event.target.matches('select,input[type="date"]')) return;
      if (!form.reportValidity()) return;
      if (typeof form.requestSubmit === 'function') form.requestSubmit();
    });
  });
  document.querySelectorAll('[data-sd152-view]').forEach(button => {
    button.addEventListener('click', () => {
      const grid = button.dataset.sd152View === 'grid';
      document.querySelector('.sd-timeline')?.classList.toggle('sd152-showgrid', grid);
      document.querySelectorAll('[data-sd152-view]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
    });
  });
  document.querySelectorAll('.sd152-decision-actions details').forEach(details => {
    details.addEventListener('toggle', () => {
      if (details.open) details.querySelector('textarea,button')?.focus();
    });
  });
})();
