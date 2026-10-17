"""Install deposit deadlines without overwriting existing finance modules."""
from pathlib import Path
from shutil import copy2

models = Path('bookings/models.py')
urls = Path('bookings/urls.py')
reservations = Path('bookings/templates/bookings/manager_reservations.html')
for path in (models, urls, reservations):
    if not path.is_file():
        raise SystemExit(f'Missing {path}; run from the Django project root.')
if 'class PaymentTransaction(models.Model):' not in models.read_text():
    raise SystemExit('Install Payment Management first.')
for path in (models, urls, reservations):
    backup = path.with_name(path.name + '.before_deposits')
    if not backup.exists():
        copy2(path, backup)
if 'class HutDepositPolicy(models.Model):' not in models.read_text():
    models.write_text(models.read_text().rstrip() + '\n' + Path('deposit_models.txt').read_text())
if "name='deposit_dashboard'" not in urls.read_text():
    urls.write_text(urls.read_text().rstrip() + """

# Deposit policies, deadlines and overdue tracking
from .deposits import deposit_dashboard
urlpatterns += [
    path('staff/deposits/', deposit_dashboard, name='deposit_dashboard'),
]
""")
if "bookings:deposit_dashboard" not in reservations.read_text():
    source = reservations.read_text()
    source = source.replace('{% block content %}', '''{% block content %}
<p><a href="{% url 'bookings:deposit_dashboard' %}">Deposit deadlines &amp; overdue payments</a></p>''', 1)
    reservations.write_text(source)
print('Deposit deadlines installed. Run makemigrations, migrate, check and test.')
