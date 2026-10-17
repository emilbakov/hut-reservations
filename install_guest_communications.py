"""Idempotent additive installer. Run from the Django project root."""
from pathlib import Path
from shutil import copy2
models = Path("bookings/models.py")
urls = Path("bookings/urls.py")
dashboard = Path("bookings/templates/bookings/manager_reservations.html")
for f in (models, urls, dashboard):
    if not f.is_file():
        raise SystemExit(f"Missing {f}; run from Django project root.")
if "class HutDepositPolicy(models.Model):" not in models.read_text():
    raise SystemExit("Deposit Deadlines must be installed first.")
for f in (models, urls, dashboard):
    backup = f.with_name(f.name + ".before_guest_communications")
    if not backup.exists(): copy2(f, backup)
if "class HutMessageTemplate(models.Model):" not in models.read_text():
    models.write_text(models.read_text().rstrip() + "\n" + Path("communications_models.txt").read_text())
if "name='communications_dashboard'" not in urls.read_text():
    urls.write_text(urls.read_text().rstrip() + """

from .communications import communications_dashboard
urlpatterns += [
    path('staff/communications/', communications_dashboard, name='communications_dashboard'),
]
""")
if "bookings:communications_dashboard" not in dashboard.read_text():
    dashboard.write_text(dashboard.read_text().replace("{% block content %}", """{% block content %}
<p><a href="{% url 'bookings:communications_dashboard' %}">Guest communications &amp; message history</a></p>""", 1))

# Optional customization of the existing booking confirmation function.
views = Path("bookings/views.py")
if views.is_file():
    source = views.read_text()
    start = source.find("def send_confirmation(request, reservation):")
    end = source.find("\ndef ", start + 4) if start >= 0 else -1
    if end == -1:
        end = len(source)
    original = source[start:end] if start >= 0 else ""
    if start >= 0 and "custom_confirmation_subject" not in original:
        marker = '    body = render_to_string('
        send = 'send_mail(f"Your reservation at {settings.HUT_NAME}", body, None, [recipient])'
        if marker in original and send in original:
            backup = views.with_name(views.name + ".before_guest_communications")
            if not backup.exists(): copy2(views, backup)
            injection = (
                '    custom_confirmation_subject = None\n'
                '    custom_confirmation_body = None\n'
                '    from .deposits import single_hut_id\n'
                '    from .models import HutMessageTemplate, Hut\n'
                '    from .communications import render_message\n'
                '    hut_id = single_hut_id(reservation)\n'
                '    if hut_id and HutMessageTemplate.objects.filter(\n'
                '        hut_id=hut_id, message_type="confirmation", enabled=True\n'
                '    ).exists():\n'
                '        custom_confirmation_subject, custom_confirmation_body = render_message(\n'
                '            reservation, Hut.objects.get(pk=hut_id), "confirmation"\n'
                '        )\n'
            )
            original = original.replace(marker, injection + marker, 1)
            original = original.replace('    recipients = [reservation.email]',
                '    if custom_confirmation_body is not None:\n'
                '        body = custom_confirmation_body\n'
                '    recipients = [reservation.email]', 1)
            original = original.replace(send,
                'send_mail(custom_confirmation_subject or f"Your reservation at {settings.HUT_NAME}", body, None, [recipient])', 1)
            views.write_text(source[:start] + original + source[end:])
        else:
            print("NOTICE: confirmation function differs; leaving unchanged.")
else:
    print("NOTICE: bookings/views.py not found; confirmation customization unavailable.")

print("Guest communications installed. Run makemigrations, migrate, check, and tests.")
