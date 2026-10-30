/* Presentation only. The established booking script owns quantities, prices and refreshes. */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';
  const form = document.getElementById('ph-reservation-form');
  const dates = document.getElementById('ph-date-form');
  const preview = document.getElementById('b170-price-summary');
  if (!form) {
    dates?.addEventListener('submit', () => {
      const url = new URL(dates.action);
      url.hash = 'rooms';
      dates.action = url.href;
    });
    return;
  }
  if (!preview) return;

  function syncPreview() {
    const guest = document.getElementById('guest-details');
    preview.hidden = !guest || guest.hidden;
    const lines = document.getElementById('ph-summary-lines');
    const target = document.getElementById('b170-summary-lines');
    if (lines && target) target.replaceChildren(...Array.from(lines.children, node => node.cloneNode(true)));
    const prompt = document.getElementById('ph-total-prompt');
    const value = document.getElementById('ph-total-value');
    const total = document.getElementById('b170-total');
    const selected = Boolean(prompt && prompt.hidden);
    if (total) {
      total.textContent = (selected ? value : prompt)?.textContent.trim() || '';
      total.classList.toggle('b170-total-prompt', !selected);
    }
    const next = document.getElementById('b170-continue');
    if (next) {
      next.setAttribute('href', selected ? '#guest-details' : '#rooms');
      next.querySelector('[data-continue-label]').textContent = selected ? next.dataset.labelReady : next.dataset.labelEmpty;
    }
    const sidebar = document.querySelector('.b170-sidebar');
    if (sidebar) sidebar.classList.toggle('b170-summary-tall', sidebar.getBoundingClientRect().height > window.innerHeight - 32);
  }

  syncPreview();
  new MutationObserver(syncPreview).observe(form, {
    subtree: true, childList: true, characterData: true,
    attributes: true, attributeFilter: ['hidden']
  });
  window.addEventListener('pageshow', syncPreview);
  window.addEventListener('resize', syncPreview);
});
