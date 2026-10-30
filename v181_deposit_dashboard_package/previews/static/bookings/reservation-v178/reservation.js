// Printing is optional; the receipt and all operational forms work without JS.
(() => {
  const printButton = document.querySelector('[data-r178-print]');
  if (printButton) {
    printButton.hidden = false;
    printButton.addEventListener('click', () => window.print());
  }
})();
