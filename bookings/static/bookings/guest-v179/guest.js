(() => {
  'use strict';
  const form = document.getElementById('gss-request-form');
  if (form) {
    const type = document.getElementById('gss-request-type');
    const arrival = document.getElementById('gss-check-in');
    const departure = document.getElementById('gss-check-out');
    function resetDates() { arrival.setCustomValidity(''); departure.setCustomValidity(''); }
    function sync() {
      const cancellation = type.value === 'cancellation';
      form.querySelectorAll('.g179-date-field').forEach(field => { field.hidden = cancellation; });
      [arrival, departure].forEach(input => { input.disabled = cancellation; input.required = !cancellation; });
      resetDates();
    }
    type.addEventListener('change', sync);
    [arrival, departure].forEach(input => input.addEventListener('input', resetDates));
    sync();
    form.addEventListener('submit', event => {
      if (type.value === 'change' && arrival.value && departure.value && departure.value <= arrival.value) {
        event.preventDefault();
        departure.setCustomValidity(form.dataset.dateOrderError);
        departure.reportValidity();
      }
    });
  }
  const errors = document.getElementById('g179-errors');
  if (errors) {
    errors.focus({ preventScroll: true });
    errors.scrollIntoView({ block: 'start' });
    errors.querySelectorAll('a[href^="#"]').forEach(link => link.addEventListener('click', event => {
      const target = document.getElementById(link.getAttribute('href').slice(1));
      if (target) { event.preventDefault(); target.focus(); }
    }));
  }
  const messageForm = document.querySelector('.g179-message-form');
  if (messageForm) {
    const input = messageForm.querySelector('textarea');
    input.addEventListener('input', () => input.setCustomValidity(''));
    messageForm.addEventListener('submit', event => {
      if (!input.value.trim()) {
        event.preventDefault(); input.setCustomValidity(messageForm.dataset.emptyError); input.reportValidity();
      }
    });
  }
})();
