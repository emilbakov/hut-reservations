"""Install v46 against the live v45 Staff Hub; fail closed on unexpected layouts."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import shutil

ROOT = Path(__file__).resolve().parent.parent
VIEW = ROOT / 'floorplans/staff_hub.py'
TEMPLATE = ROOT / 'floorplans/templates/floorplans/staff_hub.html'
MODULE = ROOT / 'floorplans/forecast_comparison_v46.py'
FRAGMENT = Path(__file__).resolve().parent / 'comparison_fragment.html'

if not all(p.exists() for p in (VIEW, TEMPLATE, FRAGMENT)):
    raise SystemExit('Missing Staff Hub or v46 fragment. No changes made.')
view = VIEW.read_text(encoding='utf-8')
template = TEMPLATE.read_text(encoding='utf-8')
if 'V46_COMPARISON_START' in template or 'comparison_v46' in view or MODULE.exists():
    raise SystemExit('v46 appears to be installed already; no changes made.')
import_anchor = 'from .forecast_dates_v45 import select_forecast_start  # V45_FORECAST_DATES\n'
view_anchor = '        # V44_FORECAST_CSV: only accessible inside the manager-only branch.\n'
template_anchor = '<!-- V38_FORECAST_END -->'
for content, needle in ((view, import_anchor), (view, view_anchor), (template, template_anchor)):
    if content.count(needle) != 1:
        raise SystemExit(f'Expected exactly one anchor: {needle!r}. No changes made.')
if 'forecast_display_v45' not in view or 'forecast_display_v45' not in template:
    raise SystemExit('v45 forecast missing; install v45 first.')
new_view = view.replace(import_anchor, import_anchor + 'from .forecast_comparison_v46 import compare_forecast  # V46_COMPARISON\n', 1)
new_view = new_view.replace(view_anchor, "        context['comparison_v46'] = compare_forecast(hut, forecast_start, context['forecast_display_v45'])  # V46_COMPARISON\n" + view_anchor, 1)
new_template = template.replace(template_anchor, template_anchor + '\n' + FRAGMENT.read_text(encoding='utf-8'), 1)
ast.parse(new_view, filename=str(VIEW))
ast.parse((Path(__file__).resolve().parent / 'forecast_comparison_v46.py').read_text(encoding='utf-8'))
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
for target in (VIEW, TEMPLATE):
    backup = target.with_name(target.name + f'.bak_v46_{stamp}')
    shutil.copy2(target, backup)
    print(f'Backup: {backup}')
shutil.copy2(Path(__file__).resolve().parent / 'forecast_comparison_v46.py', MODULE)
VIEW.write_text(new_view, encoding='utf-8')
TEMPLATE.write_text(new_template, encoding='utf-8')
print('v46 installed. Run Django checks and verify manager/cleaner permissions before restarting.')
