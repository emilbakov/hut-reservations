from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase

class KarlakLanguageLastV158Tests(SimpleTestCase):
    def test_public_order(self):
        s=(Path(settings.BASE_DIR)/'bookings/templates/bookings/public_base_v124.html').read_text()
        self.assertLess(s.index('class="pub-brand"'),s.index('class="pub-nav"'))
        self.assertLess(s.index('class="pub-nav"'),s.index('include "bookings/language_v147.html"'))
        self.assertIn('karlak_language_last_v158.css',s)

    def test_legacy_order(self):
        s=(Path(settings.BASE_DIR)/'bookings/templates/bookings/base.html').read_text()
        self.assertLess(s.index('class="desktop-nav"'),s.index('include "bookings/language_v147.html"'))
        self.assertIn('karlak_language_last_v158.css',s)

    def test_css_language_last(self):
        s=(Path(settings.BASE_DIR)/'bookings/static/bookings/karlak_language_last_v158.css').read_text()
        self.assertIn('.pub-nav { order:1;',s)
        self.assertIn('.sd147-language { order:2;',s)
