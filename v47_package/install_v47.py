"""Install v47 against v46, with fail-closed anchors and timestamped backups."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import shutil

ROOT = Path(__file__).resolve().parent.parent
PKG = Path(__file__).resolve().parent
VIEW = ROOT / 'floorplans/staff_hub.py'
TEMPLATE = ROOT / 'floorplans/templates/floorplans/staff_hub.html'
MODULE = ROOT / 'floorplans/comparison_export_v47.py'
SOURCE = PKG / 'comparison_export_v47.py'
FRAGMENT = PKG / 'export_link.html'
if not all(p.exists() for p in (VIEW, TEMPLATE, SOURCE, FRAGMENT)):
    raise SystemExit('Missing required file. No changes made.')
view = VIEW.read_text(encoding='utf-8')
template = TEMPLATE.read_text(encoding='utf-8')
if MODULE.exists() or 'V47_COMPARISON_EXPORT' in view or 'V47_COMPARISON_EXPORT' in template:
    raise SystemExit('v47 already installed; no changes made.')
import_anchor = 'from .forecast_comparison_v46 import compare_forecast  # V46_COMPARISON\n'
view_anchor = "        context['comparison_v46'] = compare_forecast(hut, forecast_start, context['forecast_display_v45'])  # V46_COMPARISON\n"
template_anchor = '<!-- V46_COMPARISON_END -->'
for data, anchor in ((view, import_anchor), (view, view_anchor), (template, template_anchor)):
    if data.count(anchor) != 1:
        raise SystemExit(f'Missing/duplicate v46 anchor: {anchor!r}. No changes made.')
new_view = view.replace(import_anchor, import_anchor + 'from .comparison_export_v47 import export_comparison_csv  # V47_COMPARISON_EXPORT\n', 1)
new_view = new_view.replace(view_anchor, view_anchor + "        if request.GET.get('comparison_export') == 'csv':  # V47_COMPARISON_EXPORT\n            return export_comparison_csv(hut, context['comparison_v46'])\n", 1)
new_template = template.replace(template_anchor, FRAGMENT.read_text(encoding='utf-8') + template_anchor, 1)
ast.parse(new_view, filename=str(VIEW))
ast.parse(SOURCE.read_text(encoding='utf-8'), filename=str(SOURCE))
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
for target in (VIEW, TEMPLATE):
    backup = target.with_name(target.name + f'.bak_v47_{stamp}')
    shutil.copy2(target, backup)
    print('Backup:', backup)
shutil.copy2(SOURCE, MODULE)
VIEW.write_text(new_view, encoding='utf-8')
TEMPLATE.write_text(new_template, encoding='utf-8')
print('v47 installed. Run Django checks and test manager/cleaner access before restarting.')
