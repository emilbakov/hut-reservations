#!/usr/bin/env python3
"""SummitDesk v114: template-only reservation quick-view installer.

Fails closed if the expected v113 template is not in place. Backs up first,
then atomically replaces one template file. Never changes reservation data.
"""
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PKG = Path(__file__).resolve().parent
PAGE = ROOT / 'bookings/templates/bookings/calendar_timeline.html'
MARKER = 'SUMMITDESK_QUICKVIEW_V114'


def stop(reason):
    raise SystemExit(reason + ' No changes made.')


def build(old):
    if MARKER in old:
        stop('v114 is already installed.')
    if not all(token in old for token in (
        '{% extends "bookings/base.html" %}',
        'class="sd-timeline"',
        'class="sd-booking {% if bar.status',
        'data-code="{{ bar.code }}"',
        '{% url "bookings:calendar_move" %}',
        '{% url \'bookings:calendar_edit\' bar.code %}',
    )):
        stop('Expected v113 reservation calendar not found.')
    # Require unique hooks to ensure template changes are safe to apply.
    hooks = {
        '</style>': 1,
        'data-hut="{{ row.room.hut_id }}" title="{{ bar.guest }}': 1,
        '</div>\n<script>\n(function(){': 1,
        '</script>\n{% endblock %}': 1,
    }
    for needle, count in hooks.items():
        if old.count(needle) != count:
            stop('Unexpected timeline structure at ' + repr(needle))
    css = (PKG / 'quick_view.css').read_text(encoding='utf-8')
    js = (PKG / 'quick_view.js').read_text(encoding='utf-8')
    dialog = (PKG / 'quick_view.html').read_text(encoding='utf-8')
    if '</style' in css.lower() or '</script' in js.lower():
        stop('Unexpected closing tags in bundled styles or scripts.')

    # Existing anchors remain real edit links when JavaScript is unavailable.
    data_hook = 'data-hut="{{ row.room.hut_id }}" title="{{ bar.guest }}'
    extra = (
        'data-guest="{{ bar.guest }}" '
        'data-beds="{{ bar.beds }}" '
        'data-status="{{ bar.status }}" '
        'data-check-in="{{ bar.check_in|date:\'Y-m-d\' }}" '
        'data-check-out="{{ bar.check_out|date:\'Y-m-d\' }}" '
        'data-room-name="{{ row.room.name }}" '
        'data-hut-name="{{ row.room.hut.name }}" '
    )
    new = old.replace(data_hook, 'data-hut="{{ row.room.hut_id }}" ' + extra + 'title="{{ bar.guest }}', 1)
    new = new.replace(' · Select to edit"', ' · Select to review"', 1)
    new = new.replace('</style>', '\n' + css + '\n</style>', 1)
    new = new.replace('</div>\n<script>\n(function(){', '</div>\n' + dialog + '\n<script>\n(function(){', 1)
    new = new.replace('</script>\n{% endblock %}', '</script>\n<script>\n' + js + '\n</script>\n{% endblock %}', 1)
    if any(new.count(token) != 1 for token in (
        MARKER, 'id="sd-quickview"', 'id="sd-quick-edit"',
        'data-check-out="{{ bar.check_out',
    )):
        stop('Internal validation failed.')
    if old.count('calendar_move') != new.count('calendar_move') or old.count('calendar_edit') != new.count('calendar_edit'):
        stop('Existing calendar navigation changed unexpectedly.')
    return new


def main():
    if not PAGE.is_file():
        stop('Missing calendar timeline template.')
    old = PAGE.read_text(encoding='utf-8')
    new = build(old)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup = PAGE.with_name(PAGE.name + '.bak_v114_' + stamp)
    shutil.copy2(PAGE, backup)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                prefix='.calendar_timeline_v114_', suffix='.html',
                dir=PAGE.parent, delete=False) as temp:
            temp.write(new)
            temp_path = Path(temp.name)
        os.chmod(temp_path, PAGE.stat().st_mode & 0o777)
        os.replace(temp_path, PAGE)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        shutil.copy2(backup, PAGE)
        raise
    print('SummitDesk v114 installed: reservation quick view.')
    print('Backup:', backup)
    print('No migrations or view changes. Run Django checks and browser tests before restart.')


if __name__ == '__main__':
    main()
