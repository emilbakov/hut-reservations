/* Presentation only. Reservation validation and prices are authoritative on the server. */
document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('ph-reservation-form');
  if (form) {
    const total = document.getElementById('ph-total');
    const nights = Number(form.querySelector('input[name="check_in"]')?.value && form.querySelector('input[name="check_out"]')?.value ?
      Math.round((Date.parse(form.querySelector('input[name="check_out"]').value + 'T00:00:00Z') - Date.parse(form.querySelector('input[name="check_in"]').value + 'T00:00:00Z')) / 86400000) : 0);
    const fields = Array.from(form.querySelectorAll('input.beds'));
    function updateTotal() {
      let cents = 0;
      fields.forEach(function (input) {
        const quantity = Math.max(0, Number.parseInt(input.value, 10) || 0);
        const price = Number(input.dataset.price || 0);
        if (Number.isFinite(price)) cents += Math.round(price * 100) * quantity * Math.max(0, nights);
      });
      if (total) total.textContent = (cents / 100).toFixed(2);
    }
    fields.forEach(function (input) { input.addEventListener('input', updateTotal); input.addEventListener('change', updateTotal); });
    updateTotal();
    form.addEventListener('submit', function () {
      form.querySelectorAll('button[type="submit"]').forEach(function (button) {
        button.disabled = true;
        button.textContent = 'Sending request…';
      });
    });
  }
  const dates = document.getElementById('ph-date-form');
  if (dates) {
    const arrival = dates.querySelector('[name="check_in"]');
    const departure = dates.querySelector('[name="check_out"]');
    if (arrival && departure) {
      arrival.addEventListener('change', function () {
        if (!arrival.value) return;
        const next = new Date(arrival.value + 'T00:00:00Z');
        if (Number.isNaN(next.getTime())) return;
        next.setUTCDate(next.getUTCDate() + 1);
        const minimum = next.toISOString().slice(0, 10);
        departure.min = minimum;
        if (departure.value && departure.value < minimum) departure.value = '';
      });
    }
  }
});
