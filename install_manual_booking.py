"""Run once from project root. Back up and update model + URLs."""
from pathlib import Path
import re

models = Path("bookings/models.py")
urls = Path("bookings/urls.py")
model_text = models.read_text()
url_text = urls.read_text()

# Update only Reservation.email, not any other model's email field.
pattern = r'(class Reservation\(models\.Model\):[\s\S]*?\n\s*email = models\.EmailField\()\)'
match = re.search(pattern, model_text)
if not match:
    if not re.search(r'class Reservation\(models\.Model\):[\s\S]*?email = models\.EmailField\(blank=True\)', model_text):
        raise SystemExit("Cannot locate Reservation.email; no changes made.")
else:
    model_text = model_text[:match.start()] + match.group(1) + 'blank=True)' + model_text[match.end():]

if 'name="manual_booking"' not in url_text and "name='manual_booking'" not in url_text:
    if 'urlpatterns' not in url_text or 'from django.urls import path' not in url_text:
        raise SystemExit("Unexpected bookings/urls.py layout; no changes made.")
    url_text += '''\n# Staff manual reservations\nfrom . import manual_bookings\nurlpatterns += [\n    path("staff/reservations/new/", manual_bookings.manual_booking, name="manual_booking"),\n]\n'''

for path, new_text in ((models, model_text), (urls, url_text)):
    if path.read_text() != new_text:
        backup = path.with_name(path.name + ".before_manual_booking")
        if not backup.exists():
            backup.write_text(path.read_text())
        path.write_text(new_text)
        print("Updated", path, "backup:", backup)
    else:
        print("Already configured:", path)
