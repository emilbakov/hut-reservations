"""Regression checks for right-aligned Karlak public links (v156)."""
from pathlib import Path
from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase

class KarlakRightLinksV156Tests(SimpleTestCase):
    def test_public_layouts_load_v156_styles_after_prior_nav(self):
        for name in ('bookings/public_base_v124.html', 'bookings/base.html'):
            with self.subTest(name=name):
                source = get_template(name).template.source
                self.assertIn('karlak_links_right_v156.css', source)
                self.assertGreater(source.index('karlak_links_right_v156.css'), source.index('karlak_nav_v154.css'))
                if 'karlak_links_v155.css' in source:
                    self.assertGreater(source.index('karlak_links_right_v156.css'), source.index('karlak_links_v155.css'))

    def test_footer_order_brand_contact_links(self):
        source = get_template('bookings/public_footer_v149.html').template.source
        grid = source.split('class="pub149-footer-grid">', 1)[1]
        self.assertLess(grid.index('karlak-footer-brand'), grid.index('<nav '))
        self.assertIn('Footer navigation', grid)
        self.assertIn('bookings:staff_login', grid)

    def test_right_alignment_rules_present(self):
        css = (Path(settings.BASE_DIR) / 'bookings/static/bookings/karlak_links_right_v156.css').read_text()
        self.assertIn('margin-left: auto;', css)
        self.assertIn('justify-content: flex-end;', css)
        self.assertIn('justify-self: end;', css)
        self.assertIn('grid-template-columns: minmax(0, 1fr);', css)
