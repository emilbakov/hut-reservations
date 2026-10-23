"""Static regression checks for the Karlak navigation brand patch."""
from pathlib import Path
from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase

class KarlakNavigationV154Tests(SimpleTestCase):
    def test_stylesheet_exists_and_clears_background(self):
        css = Path(settings.BASE_DIR) / 'bookings/static/bookings/karlak_nav_v154.css'
        content = css.read_text()
        self.assertIn('background: transparent !important', content)
        self.assertIn('72px', content)

    def test_public_and_staff_navigation_use_karlak(self):
        for template in ('bookings/public_base_v124.html', 'bookings/base.html',
                         'floorplans/includes/summitdesk_nav.html'):
            with self.subTest(template=template):
                source = get_template(template).template.source
                self.assertIn('karlak_nav_v154.css', source)
                self.assertIn('Karlak', source)
