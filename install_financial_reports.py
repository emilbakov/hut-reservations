"""Install financial reports without overwriting existing reservation code."""
from pathlib import Path
from shutil import copy2

urls = Path("bookings/urls.py")
dashboard = Path("bookings/templates/bookings/dashboard.html")
if not urls.exists():
    raise SystemExit("Run from Django project root; bookings/urls.py missing.")
if not Path("bookings/models.py").read_text().find("class PaymentTransaction(models.Model):") >= 0:
    raise SystemExit("Payment Management must be installed first.")
for p in (urls, dashboard):
    if p.exists() and not p.with_name(p.name + ".before_financial_reports").exists():
        copy2(p, p.with_name(p.name + ".before_financial_reports"))
source = urls.read_text()
if "name='financial_dashboard'" not in source:
    urls.write_text(source.rstrip() + """

# Financial dashboard and CSV export
from .financial_reports import financial_dashboard, financial_export
urlpatterns += [
    path('staff/finances/', financial_dashboard, name='financial_dashboard'),
    path('staff/finances/export/', financial_export, name='financial_export'),
]
""")
if dashboard.exists():
    html = dashboard.read_text()
    if "bookings:financial_dashboard" not in html:
        anchor = '<p><a href="{% url \'bookings:financial_dashboard\' %}">Financial dashboard &amp; CSV report</a></p>'
        html = html.replace("{% block content %}", "{% block content %}\n" + anchor, 1)
        dashboard.write_text(html)
print("Installed finance report URLs and dashboard link; no migrations required.")
