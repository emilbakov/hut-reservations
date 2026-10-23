"""Regression checks for v155 public navigation/footer link placement."""
from pathlib import Path
from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase


class KarlakLinksV155Tests(SimpleTestCase):
    def test_public_shell_loads_left_links_stylesheet(self):
        for name in ('bookings/public_base_v124.html', 'bookings/base.html'):
            with self.subTest(name=name):
                source = get_template(name).template.source
                self.assertIn('karlak_links_v155.css', source)
                self.assertIn('karlak_nav_v154.css', source)

    def test_footer_navigation_position_accounts_for_v156_override(self):
        source = get_template('bookings/public_footer_v149.html').template.source
        grid = source.split('class="pub149-footer-grid">', 1)[1]
        # v156 intentionally moves Useful links to the rightmost column.
        if 'karlak_links_right_v156.css' in get_template('bookings/public_base_v124.html').template.source:
            self.assertGreater(grid.index('<nav '), grid.index('karlak-footer-brand'))
        else:
            self.assertLess(grid.index('<nav '), grid.index('karlak-footer-brand'))
        self.assertIn('Footer navigation', source)
        self.assertIn('bookings:staff_login', source)

    def test_styles_keep_left_alignment_and_mobile_stack(self):
        css = (Path(settings.BASE_DIR) / 'bookings/static/bookings/karlak_links_v155.css').read_text()
        self.assertIn('justify-content: flex-start', css)
        self.assertIn('grid-template-columns: minmax(0, 1fr);', css)
        self.assertIn('.pub149-footer .pub149-footer-grid > nav', css)
