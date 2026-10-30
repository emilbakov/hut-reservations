"""Isolated PostgreSQL regression settings. Refuse any live database name."""
import os
import re
from .settings_v145_test import *
from .settings_postgres import DATABASES as _PRODUCTION_DATABASES
_trial_name = os.environ.get('HUT_DEPOSIT_TEST_DB', '')
if not re.fullmatch(r'summitdesk_v180_test_[0-9]+_[0-9a-f]{8}', _trial_name):
    raise RuntimeError('Use the v180 isolated PostgreSQL verification script; no live database fallback is allowed.')
DATABASES = {'default': {**_PRODUCTION_DATABASES['default'], 'NAME': _trial_name,
    'TEST': {'NAME': _trial_name}, 'CONN_MAX_AGE': 0}}
