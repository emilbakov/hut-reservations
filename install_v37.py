#!/usr/bin/env python3
"""Install v37 additions without replacing existing hub implementation."""
from pathlib import Path
from datetime import datetime
import shutil

root = Path(__file__).resolve().parent
project = Path.cwd()
view = project / 'floorplans/staff_hub.py'
template = project / 'floorplans/templates/floorplans/staff_hub.html'
if not view.is_file() or not template.is_file():
    raise SystemExit('Run installer from Django project root (floorplans files missing).')
view_text = view.read_text()
tpl_text = template.read_text()
if 'V37_MANAGER_OVERVIEW' in view_text or 'v37-daily-overview' in tpl_text:
    raise SystemExit('v37 appears already installed; no changes made.')
checks = [
    ('view context marker', "    return render(request, 'floorplans/staff_hub.html', context)" in view_text),
    ('view manager branch', '    if manager:\n' in view_text),
    ('template insertion marker', '<section class="section"><h2>Workspace</h2>' in tpl_text),
    ('manager insights', 'v36-insights-title' in tpl_text),
]
for label, ok in checks:
    if not ok:
        raise SystemExit(f'Expected {label} not found. No changes made; send your current files for review.')

snippet = '''    # V37_MANAGER_OVERVIEW: stay-date figures for today, confirmed bookings only.
    if manager:
        from decimal import Decimal
        from bookings.models import ReservationItem
        from django.db.models import Q
        daily_items = ReservationItem.objects.filter(
            room__hut=hut,
            room__is_active=True,
            reservation__status='confirmed',
        ).filter(
            Q(reservation__check_in__lte=today, reservation__check_out__gt=today)
            | Q(reservation__check_in=tomorrow)
        ).select_related('reservation')
        confirmed_today = 0
        confirmed_value_today = Decimal('0.00')
        arrivals_tomorrow = 0
        for item in daily_items:
            reservation = item.reservation
            if reservation.check_in <= today < reservation.check_out:
                confirmed_today += item.beds
                confirmed_value_today += item.price_per_night * item.beds
            if reservation.check_in == tomorrow:
                arrivals_tomorrow += item.beds
        context.update({
            'v37_confirmed_beds_today': confirmed_today,
            'v37_booking_value_today': confirmed_value_today,
            'v37_arrivals_tomorrow': arrivals_tomorrow,
        })
'''
new_view = view_text.replace("    return render(request, 'floorplans/staff_hub.html', context)", snippet + "    return render(request, 'floorplans/staff_hub.html', context)", 1)
section = '''<!-- v37-daily-overview -->
{% if manager %}
<section class="section" aria-labelledby="v37-daily-title">
  <h2 id="v37-daily-title">Today's confirmed booking snapshot</h2>
  <div class="grid">
    <div class="card"><div class="muted">Confirmed occupied bed places today</div><div class="num">{{ v37_confirmed_beds_today }}</div></div>
    <div class="card"><div class="muted">Confirmed booking value for tonight</div><div class="num">{{ v37_booking_value_today|floatformat:2 }}</div><div class="muted">Estimated booking value, not payments received</div></div>
    <div class="card"><div class="muted">Tomorrow's confirmed arrivals · bed places</div><div class="num">{{ v37_arrivals_tomorrow }}</div></div>
  </div>
  <p class="muted">Tonight uses confirmed reservations only, with check-out excluded. Values use the stored per-bed nightly rate. The existing top-row occupied/arrival/departure counts include pending holds.</p>
</section>
{% endif %}
'''
new_tpl = tpl_text.replace('<section class="section"><h2>Workspace</h2>', section + '<section class="section"><h2>Workspace</h2>', 1)
# Verify Python syntax before writing anything.
compile(new_view, str(view), 'exec')
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup = project / f'v37_backup_{stamp}'
backup.mkdir()
shutil.copy2(view, backup / 'staff_hub.py')
shutil.copy2(template, backup / 'staff_hub.html')
try:
    view.write_text(new_view)
    template.write_text(new_tpl)
except Exception:
    shutil.copy2(backup / 'staff_hub.py', view)
    shutil.copy2(backup / 'staff_hub.html', template)
    raise
print('v37 installed. Backup:', backup)
print('Next: python manage.py check; restart gunicorn if successful.')
