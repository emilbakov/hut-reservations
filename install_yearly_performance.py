"""Run once from the project root, after copying yearly_reports.py and template."""
from pathlib import Path

path = Path('bookings/urls.py')
original = path.read_text()
if 'name="yearly_performance"' in original or "name='yearly_performance'" in original:
    print('Yearly report routes already installed.')
else:
    backup = path.with_suffix('.py.before_yearly_performance')
    backup.write_text(original)
    path.write_text(original + '''\n# Annual hut performance report\nfrom . import yearly_reports\nurlpatterns += [\n    path("staff/performance/", yearly_reports.yearly_performance, name="yearly_performance"),\n    path("staff/performance/export/", yearly_reports.yearly_performance_export, name="yearly_performance_export"),\n]\n''')
    print('Added annual performance routes. Backup:', backup)
