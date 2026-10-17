"""Install lifecycle feature additively, with backups and idempotent edits."""
from pathlib import Path
from shutil import copy2
models = Path("bookings/models.py")
urls = Path("bookings/urls.py")
deposit_template = Path("bookings/templates/bookings/deposit_dashboard.html")
for f in (models, urls, deposit_template):
    if not f.is_file():
        raise SystemExit(f"Missing {f}. Install Deposit Deadlines first.")
source = models.read_text()
if "class HutDepositPolicy(models.Model):" not in source:
    raise SystemExit("Deposit Deadlines is not installed.")
if "class ReservationLifecycleEvent(models.Model):" not in source:
    b = models.with_name(models.name + ".before_lifecycle")
    if not b.exists(): copy2(models, b)
    source += "\n" + Path("lifecycle_models.txt").read_text()
    models.write_text(source)
# Extend the existing policy in place, preserving its other fields.
source = models.read_text()
policy_start = source.index("class HutDepositPolicy(models.Model):")
policy_end = source.index("\nclass ", policy_start + 1)
policy_block = source[policy_start:policy_end]
if "auto_cancel_enabled" not in policy_block:
    b = models.with_name(models.name + ".before_lifecycle")
    if not b.exists(): copy2(models, b)
    needle = "class HutDepositPolicy(models.Model):"
    source = source.replace(needle, needle + """
    grace_days = models.PositiveSmallIntegerField(default=2)
    auto_cancel_enabled = models.BooleanField(default=False)
""", 1)
    models.write_text(source)
source = urls.read_text()
if "name='lifecycle_dashboard'" not in source:
    b = urls.with_name(urls.name + ".before_lifecycle")
    if not b.exists(): copy2(urls, b)
    urls.write_text(source.rstrip() + """

# Reservation deposit lifecycle
from .lifecycle import lifecycle_dashboard
urlpatterns += [
    path('staff/deposits/lifecycle/', lifecycle_dashboard, name='lifecycle_dashboard'),
]
""")
source = deposit_template.read_text()
if "bookings:lifecycle_dashboard" not in source:
    b = deposit_template.with_name(deposit_template.name + ".before_lifecycle")
    if not b.exists(): copy2(deposit_template, b)
    deposit_template.write_text(source.replace("{% block content %}", """{% block content %}
<p><a href="{% url 'bookings:lifecycle_dashboard' %}">Deposit lifecycle &amp; audit log →</a></p>""", 1))
print("Lifecycle installed. Run makemigrations, migrate, check, and tests.")
