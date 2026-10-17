"""Add guest self-service and manager review without changing existing URLs."""
from pathlib import Path
from shutil import copy2
models = Path("bookings/models.py")
urls = Path("bookings/urls.py")
dashboard = Path("bookings/templates/bookings/manager_reservations.html")
for file in (models, urls, dashboard):
    if not file.is_file():
        raise SystemExit(f"Missing {file}. Run from the Django project root.")
if "class HutDepositPolicy(models.Model):" not in models.read_text():
    raise SystemExit("Install Deposit Deadlines first.")
for file in (models, urls, dashboard):
    backup = file.with_name(file.name + ".before_guest_self_service")
    if not backup.exists(): copy2(file, backup)
if "class GuestAccessLink(models.Model):" not in models.read_text():
    text = models.read_text()
    text += """

def make_guest_access_token():
    import secrets
    return secrets.token_urlsafe(32)

""" + Path("self_service_models.txt").read_text()
    models.write_text(text)
if "name='guest_self_service'" not in urls.read_text():
    urls.write_text(urls.read_text().rstrip() + """

from .self_service import guest_self_service, guest_requests_dashboard
urlpatterns += [
    path('guest/manage/<str:token>/', guest_self_service, name='guest_self_service'),
    path('staff/guest-requests/', guest_requests_dashboard, name='guest_requests_dashboard'),
]
""")
if "bookings:guest_requests_dashboard" not in dashboard.read_text():
    dashboard.write_text(dashboard.read_text().replace("{% block content %}", """{% block content %}
<p><a href="{% url 'bookings:guest_requests_dashboard' %}">Guest change &amp; cancellation requests</a></p>""", 1))
print("Installed. Run makemigrations, migrate, check, and tests.")
