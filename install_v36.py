#!/usr/bin/env python3
"""SummitDesk v36: safely add manager insights links to the existing staff hub."""
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

root = Path(__file__).resolve().parent
# The script is extracted to the Django project root.
target = root / 'floorplans' / 'templates' / 'floorplans' / 'staff_hub.html'
if not target.is_file():
    sys.exit(f'ERROR: Existing template not found: {target}')
content = target.read_text(encoding='utf-8')
marker = '<!-- SUMMITDESK_V36_MANAGER_INSIGHTS -->'
if marker in content:
    print('v36 already installed; no changes made.')
    sys.exit(0)
anchor = '<section class="section card"><h2>{% if manager %}Today\'s cleaning tasks'
if content.count(anchor) != 1:
    sys.exit('ERROR: Expected Staff Hub insertion point not found exactly once. No changes made.')
section = '''<!-- SUMMITDESK_V36_MANAGER_INSIGHTS -->
{% if manager %}
<section class="section" aria-labelledby="v36-insights-title">
  <h2 id="v36-insights-title">Manager insights</h2>
  <nav class="links" aria-label="Manager analytics and audit tools">
    <a class="link" href="{% url 'floorplans:staff_analytics' hut.pk %}">Reservation analytics<span>Occupancy, booking trends and room utilization</span></a>
    <a class="link" href="{% url 'floorplans:staff_financial_analytics' hut.pk %}">Booking value analytics<span>Confirmed and pending booking value, room trends and CSV export</span></a>
    <a class="link" href="{% url 'floorplans:staff_audit_dashboard' hut.pk %}">Reservation audit<span>Staff activity, reservation changes and CSV export</span></a>
  </nav>
</section>
{% endif %}
'''
updated = content.replace(anchor, section + anchor, 1)
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
backup = target.with_name(f'staff_hub.html.before_v36_{stamp}.bak')
shutil.copy2(target, backup)
target.write_text(updated, encoding='utf-8')
print(f'Installed SummitDesk v36 into {target}')
print(f'Backup saved to {backup}')
