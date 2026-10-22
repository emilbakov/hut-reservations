#!/usr/bin/env python3
"""SummitDesk v49: backup-first, template-only visual forecast installer."""
from datetime import datetime, timezone
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent.parent
package = Path(__file__).resolve().parent
template = root / 'floorplans/templates/floorplans/staff_hub.html'
fragment = package / 'occupancy_chart_fragment.html'
if not template.is_file() or not fragment.is_file():
    raise SystemExit('Missing Staff Hub template or v49 fragment. No changes made.')
source = template.read_text(encoding='utf-8')
if 'V49_OCCUPANCY_CHART_START' in source:
    raise SystemExit('v49 is already installed. No changes made.')
if 'V48_COMPARISON_HIGHLIGHTS_END' not in source or 'V45_FORECAST_DATES' not in source:
    raise SystemExit('v48/v45 integration missing. Install earlier versions first. No changes made.')
anchor = '<!-- V38_FORECAST_END -->'
if source.count(anchor) != 1 or source.count('{% for day in forecast_display_v45 %}') != 1:
    raise SystemExit('Expected forecast anchors not found exactly once. No changes made.')
new = source.replace(anchor, anchor + '\n' + fragment.read_text(encoding='utf-8'), 1)
# Verify that the V38 forecast section is enclosed in a manager-only block.
# Later releases may add other sections between V38_FORECAST_END and {% endif %}.
forecast_start = new.index('<!-- V38_FORECAST_START -->')
chart_end = new.index('<!-- V49_OCCUPANCY_CHART_END -->')
manager_open = new.rfind('{% if manager %}', 0, forecast_start)
manager_close = new.find('{% endif %}', chart_end)
if manager_open < 0 or manager_close < 0:
    raise SystemExit('Manager-only placement could not be verified. No changes made.')
# No closing manager tag can occur between its opening and the chart.
# (Nested template conditionals in forecast markup are permitted.)
segment = new[manager_open:chart_end]
if '<!-- V38_FORECAST_START -->' not in segment or '<!-- V38_FORECAST_END -->' not in segment:
    raise SystemExit('Forecast manager section not found. No changes made.')
# Ensure the chart is inserted before the original manager-closing tag.
original_after_anchor = source.split(anchor, 1)[1]
if '{% endif %}' not in original_after_anchor:
    raise SystemExit('Manager closing tag missing. No changes made.')
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
backup = template.with_name(template.name + '.bak_v49_' + stamp)
shutil.copy2(template, backup)
try:
    template.write_text(new, encoding='utf-8')
except Exception:
    shutil.copy2(backup, template)
    raise
print('v49 installed. Backup:', backup)
print('Run python manage.py check and test manager/cleaner access before restarting Gunicorn.')
