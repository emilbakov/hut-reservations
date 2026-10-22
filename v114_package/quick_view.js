/* Calendar quick view: uses only information already rendered for permitted rooms. */
(function () {
  'use strict';
  const dialog = document.getElementById('sd-quickview');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const bookings = document.querySelectorAll('.sd-timeline .sd-booking');
  if (!bookings.length) return;

  const fields = {
    code: document.getElementById('sd-quick-code'),
    guest: document.getElementById('sd-quick-guest'),
    room: document.getElementById('sd-quick-room'),
    hut: document.getElementById('sd-quick-hut'),
    checkin: document.getElementById('sd-quick-checkin'),
    checkout: document.getElementById('sd-quick-checkout'),
    beds: document.getElementById('sd-quick-beds'),
    nights: document.getElementById('sd-quick-nights'),
    status: document.getElementById('sd-quick-status')
  };
  const badge = document.getElementById('sd-quick-badge');
  const edit = document.getElementById('sd-quick-edit');
  const close = document.getElementById('sd-quick-return');
  if (Object.values(fields).some(value => !value) || !badge || !edit || !close) return;

  let dragging = false;
  let ignoreClicksUntil = 0;
  function prettyDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return value || '—';
    const parsed = new Date(value + 'T12:00:00Z');
    if (Number.isNaN(parsed.getTime())) return value;
    return new Intl.DateTimeFormat(undefined, {day:'numeric', month:'short', year:'numeric', timeZone:'UTC'}).format(parsed);
  }
  function nights(from, to) {
    const a = Date.parse((from || '') + 'T00:00:00Z');
    const b = Date.parse((to || '') + 'T00:00:00Z');
    if (!Number.isFinite(a) || !Number.isFinite(b) || b <= a) return '—';
    return String(Math.round((b - a) / 86400000));
  }
  bookings.forEach(link => {
    link.title = 'View reservation details';
    link.setAttribute('aria-haspopup', 'dialog');
    link.addEventListener('dragstart', () => {dragging = true;});
    link.addEventListener('dragend', () => {dragging = false; ignoreClicksUntil = Date.now() + 450;});
    link.addEventListener('click', event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (dragging || Date.now() < ignoreClicksUntil) {event.preventDefault(); return;}
      const data = link.dataset;
      // Do not interpolate guest data into HTML: it is treated only as text.
      fields.code.textContent = data.code || '—';
      fields.guest.textContent = data.guest || '—';
      fields.room.textContent = data.roomName || '—';
      fields.hut.textContent = data.hutName || '—';
      fields.checkin.textContent = prettyDate(data.checkIn);
      fields.checkout.textContent = prettyDate(data.checkOut);
      fields.beds.textContent = data.beds || '—';
      fields.nights.textContent = nights(data.checkIn, data.checkOut);
      const isPending = data.status === 'pending';
      badge.classList.toggle('pending', isPending);
      fields.status.textContent = isPending ? 'Pending' : 'Confirmed';
      edit.href = link.href; // Same edit URL and server-side permission checks as before.
      event.preventDefault();
      dialog.showModal();
    });
  });
  close.addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    const outside = event.clientX < bounds.left || event.clientX > bounds.right ||
                    event.clientY < bounds.top || event.clientY > bounds.bottom;
    if (outside) dialog.close();
  });
})();
