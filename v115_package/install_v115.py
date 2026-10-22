#!/usr/bin/env python3
"""Install SummitDesk navigation/dashboard refresh. Run from project root."""
from pathlib import Path
from datetime import datetime
import shutil, sys
root = Path.cwd().resolve()
package = Path(__file__).resolve().parent
pairs = {
    'base.html': 'bookings/templates/bookings/base.html',
    'dashboard.html': 'bookings/templates/bookings/dashboard.html',
    'summitdesk_nav.py': 'floorplans/templatetags/summitdesk_nav.py',
    'summitdesk_nav.html': 'floorplans/templates/floorplans/includes/summitdesk_nav.html',
}
if not (root / 'manage.py').is_file() or not (root / 'bookings/urls.py').is_file():
    sys.exit('ERROR: Run installer from the Django project root.')
for source, target in pairs.items():
    if not (root / target).is_file() or not (package / source).is_file():
        sys.exit(f'ERROR: Required file missing: {target} (no changes made)')
base = (root / pairs['base.html']).read_text()
if 'sd115-nav' in base:
    sys.exit('Already installed; no changes made.')
urls = (root / 'bookings/urls.py').read_text()
for route in ('calendar_timeline', 'financial_dashboard', 'manager_stays', 'manager_reservations'):
    if f"name='{route}'" not in urls and f'name="{route}"' not in urls:
        sys.exit(f'ERROR: Missing expected URL {route}; no changes made.')
backup = root / 'summitdesk_backups' / ('navigation_dashboard_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
backup.mkdir(parents=True)
for source, target in pairs.items():
    destination = root / target
    saved = backup / target
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(destination, saved)
try:
    for source, target in pairs.items():
        shutil.copy2(package / source, root / target)
except Exception:
    for target in pairs.values():
        shutil.copy2(backup / target, root / target)
    raise
print('Installed unified dashboard and navigation.')
print('Backup:', backup)
print('Next: python manage.py check; then restart Gunicorn.')
