"""Run from project root: python install_payments.py"""
from pathlib import Path
from shutil import copy2

root = Path('bookings')
models = root / 'models.py'
urls = root / 'urls.py'
template = root / 'templates/bookings/manager_reservations.html'
for f in (models, urls, template):
    if not f.exists():
        raise SystemExit(f'Missing {f}; run from the Django project root.')
for f in (models, urls, template):
    backup = f.with_name(f.name + '.before_payments')
    if not backup.exists():
        copy2(f, backup)

model_src = models.read_text()
if 'class PaymentTransaction(models.Model):' not in model_src:
    models.write_text(model_src.rstrip() + '\n' + Path('payment_model.txt').read_text())
url_src = urls.read_text()
if "name='reservation_payments'" not in url_src:
    urls.write_text(url_src.rstrip() + "\n\n# Staff manual payment ledger\nfrom .payments import reservation_payments\nurlpatterns += [\n    path('staff/reservations/<str:code>/payments/', reservation_payments, name='reservation_payments'),\n]\n")
html = template.read_text()
if "'bookings:reservation_payments'" not in html:
    html = html.replace("<td>\n   {% if reservation.status == 'pending' %}", "<td>\n   <a href=\"{% url 'bookings:reservation_payments' reservation.code %}\">Payments</a>\n   {% if reservation.status == 'pending' %}")
    # Alternate whitespace layout, without silently omitting link.
    if "'bookings:reservation_payments'" not in html:
        html = html.replace("{% if reservation.status == 'pending' %}", "<a href=\"{% url 'bookings:reservation_payments' reservation.code %}\">Payments</a>\n   {% if reservation.status == 'pending' %}", 1)
    template.write_text(html)
print('Installed payment model, URL, and reservation link. Next: makemigrations, migrate, check, test.')
