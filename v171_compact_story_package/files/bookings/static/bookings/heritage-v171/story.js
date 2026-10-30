/* Compact, progressively enhanced history. Scroll remains native. */
(() => {
  'use strict';
  const journey = document.querySelector('[data-journey]');
  if (!journey) return;
  const chapters = Array.from(journey.querySelectorAll('[data-chapter]'));
  const triggers = Array.from(journey.querySelectorAll('[data-chapter-trigger]'));
  const photos = Array.from(journey.querySelectorAll('[data-chapter-photo]'));
  const list = journey.querySelector('.h171-chapters');
  const stage = journey.querySelector('.h171-photo-stage');
  if (!chapters.length || chapters.length !== photos.length || triggers.length !== chapters.length) return;
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  let active = 0, frame = 0;

  function select(index) {
    if (index < 0 || index >= chapters.length) return;
    chapters.forEach((chapter, i) => chapter.classList.toggle('is-active', i === index));
    triggers.forEach((trigger, i) => trigger.setAttribute('aria-pressed', String(i === index)));
    photos.forEach((photo, i) => {
      photo.hidden = i !== index;
      photo.classList.toggle('is-entering', i === index && i !== active && !reduced?.matches);
    });
    list.style.setProperty('--h171-progress', String(index / (chapters.length - 1 || 1)));
    active = index;
  }

  triggers.forEach((trigger, index) => {
    trigger.setAttribute('role', 'button');
    trigger.addEventListener('click', event => { event.preventDefault(); select(index); });
    trigger.addEventListener('keydown', event => {
      if (event.key === ' ') { event.preventDefault(); select(index); }
    });
  });
  select(0);

  function update() {
    frame = 0;
    if (reduced?.matches || document.querySelector('.h168-lightbox[open]')) return;
    const bounds = journey.getBoundingClientRect();
    if (bounds.bottom < 0 || bounds.top > window.innerHeight) return;
    const media = stage.getBoundingClientRect();
    const target = window.innerWidth <= 650 ? Math.min(window.innerHeight * .75, media.bottom + 100) : window.innerHeight * .32;
    let closest = 0;
    chapters.forEach((chapter, index) => {
      const rect = chapter.getBoundingClientRect();
      if (rect.top + Math.min(rect.height * .3, 40) <= target) closest = index;
    });
    if (closest !== active) select(closest);
  }
  function schedule() { if (!frame) frame = window.requestAnimationFrame(update); }
  window.addEventListener('scroll', schedule, {passive: true});
  window.addEventListener('resize', schedule);
  window.addEventListener('pageshow', schedule);
  journey.addEventListener('focusout', schedule);
  reduced?.addEventListener?.('change', schedule);
  schedule();
})();
