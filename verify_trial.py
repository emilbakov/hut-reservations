#!/usr/bin/env python3
"""Print model counts and a SHA-256 of canonical row data (excluding generated auth permissions/content types).
Run using `python manage.py shell --settings=... < verify_trial.py`.
"""
import hashlib
import json
from django.apps import apps
from django.db import connection

excluded = {'contenttypes.contenttype', 'auth.permission', 'sessions.session'}
print('Backend:', connection.vendor)
all_counts = {}
for model in sorted(apps.get_models(), key=lambda m: m._meta.label_lower):
    label = model._meta.label_lower
    if label in excluded or model._meta.proxy or not model._meta.managed:
        continue
    try:
        qs = model._base_manager.order_by('pk').values()
        count = qs.count()
    except Exception as exc:
        print('ERROR', label, type(exc).__name__, str(exc))
        raise
    all_counts[label] = count
    print(f'{label}: {count}')
print('TOTAL ROWS:', sum(all_counts.values()))
print('COUNTS JSON:', json.dumps(all_counts, sort_keys=True))
