"""Run once from the Django project root after copying reports.py and template."""
from pathlib import Path

urls = Path('bookings/urls.py')
original = urls.read_text()
if 'name="stay_history"' in original or "name='stay_history'" in original:
    print('Report routes already installed; no changes made.')
else:
    urls.with_suffix('.py.before_stay_history').write_text(original)
    urls.write_text(original + '''\n# Guest stay history and reports\nfrom . import reports\nurlpatterns += [\n    path("staff/history/", reports.stay_history, name="stay_history"),\n    path("staff/history/export/", reports.stay_history_export, name="stay_history_export"),\n]\n''')
    print('Added guest stay history routes to bookings/urls.py')
