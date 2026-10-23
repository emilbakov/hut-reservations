"""Regression checks for the compact language selector and approved v158 ordering.

v157 introduced compact styling; v158 intentionally moved the language selector
AFTER the links. Keep the styling checks without asserting obsolete HTML order.
"""
from pathlib import Path
from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase


class KarlakLanguageNavV157Tests(SimpleTestCase):
    def test_public_nav_links_precede_language(self):
        template = get_template('bookings/public_base_v124.html').template.source
        self.assertLess(template.index('<nav class="pub-nav"'), template.index('bookings/language_v147.html'))
        self.assertGreater(template.index('karlak_language_nav_v157.css'), template.index('karlak_links_right_v156.css'))
        self.assertGreater(template.index('karlak_language_last_v158.css'), template.index('karlak_language_nav_v157.css'))

    def test_legacy_nav_links_precede_language(self):
        template = get_template('bookings/base.html').template.source
        language = template.index('bookings/language_v147.html')
        self.assertGreater(language, template.index('<nav class="sd115-nav"'))
        self.assertGreater(language, template.index('<nav class="desktop-nav"'))
        self.assertGreater(template.index('karlak_language_nav_v157.css'), template.index('karlak_links_right_v156.css'))
        self.assertGreater(template.index('karlak_language_last_v158.css'), template.index('karlak_language_nav_v157.css'))

    def test_css_keeps_language_compact_and_v158_moves_it_last(self):
        css = (Path(settings.BASE_DIR) / 'bookings/static/bookings/karlak_language_nav_v157.css').read_text()
        self.assertIn('min-width: 36px;', css)
        self.assertIn('min-height: 36px;', css)
        self.assertIn('margin-left: 0 !important;', css)
        self.assertIn('body:not(.sd116-active)', css)
        latest = (Path(settings.BASE_DIR) / 'bookings/static/bookings/karlak_language_last_v158.css').read_text()
        self.assertIn('.pub-nav { order:1;', latest)
        self.assertIn('.sd147-language { order:2;', latest)
