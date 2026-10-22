"""Install v48 on v47. Validate all anchors before writing anything."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import shutil

ROOT = Path(__file__).resolve().parent.parent
PKG = Path(__file__).resolve().parent
VIEW = ROOT / 'floorplans/staff_hub.py'
TEMPLATE = ROOT / 'floorplans/templates/floorplans/staff_hub.html'
MODULE = ROOT / 'floorplans/comparison_highlights_v48.py'
SOURCE = PKG / 'comparison_highlights_v48.py'
FRAGMENT = PKG / 'highlights_fragment.html'
if not all(p.exists() for p in (VIEW, TEMPLATE, SOURCE, FRAGMENT)):
    raise SystemExit('Missing required file. No changes made.')
view = VIEW.read_text(encoding='utf-8')
template = TEMPLATE.read_text(encoding='utf-8')
if MODULE.exists() or 'V48_COMPARISON_HIGHLIGHTS' in view or 'V48_COMPARISON_HIGHLIGHTS' in template:
    raise SystemExit('v48 already installed. No changes made.')
if 'V47_COMPARISON_EXPORT' not in view or 'V47_COMPARISON_EXPORT_END' not in template:
    raise SystemExit('v47 is required. No changes made.')
import_anchor = 'from .forecast_comparison_v46 import compare_forecast  # V46_COMPARISON\n'
view_anchor = "        context['comparison_v46'] = compare_forecast(hut, forecast_start, context['forecast_display_v45'])  # V46_COMPARISON\n"
template_anchor = '<!-- V46_COMPARISON_END -->'
for content, needle in ((view, import_anchor), (view, view_anchor), (template, template_anchor)):
    if content.count(needle) != 1:
        raise SystemExit(f'Missing or duplicated anchor {needle!r}. No changes made.')
new_view = view.replace(import_anchor, import_anchor + 'from .comparison_highlights_v48 import build_comparison_highlights  # V48_COMPARISON_HIGHLIGHTS\n', 1)
new_view = new_view.replace(view_anchor, view_anchor + "        context['comparison_highlights_v48'] = build_comparison_highlights(context['comparison_v46'])  # V48_COMPARISON_HIGHLIGHTS\n", 1)
new_template = template.replace(template_anchor, template_anchor + '\n' + FRAGMENT.read_text(encoding='utf-8'), 1)
ast.parse(new_view, filename=str(VIEW))
ast.parse(SOURCE.read_text(encoding='utf-8'), filename=str(SOURCE))
stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
for target in (VIEW, TEMPLATE):
    backup = target.with_name(target.name + f'.bak_v48_{stamp}')
    shutil.copy2(target, backup)
    print('Backup:', backup)
shutil.copy2(SOURCE, MODULE)
VIEW.write_text(new_view, encoding='utf-8')
TEMPLATE.write_text(new_template, encoding='utf-8')
print('v48 installed. Run Django checks and test manager/cleaner permissions before restarting.')
