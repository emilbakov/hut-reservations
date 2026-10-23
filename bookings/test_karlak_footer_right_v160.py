"""v160: footer links occupy the rightmost column even without Contact."""
from pathlib import Path
from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase

class KarlakFooterRightV160Tests(SimpleTestCase):
    def test_footer_css_is_loaded_after_previous_alignment_styles(self):
        source = get_template('bookings/public_base_v124.html').template.source
        self.assertIn('karlak_footer_right_v160.css', source)
        self.assertGreater(source.index('karlak_footer_right_v160.css'), source.index('karlak_links_right_v156.css'))

    def test_footer_navigation_pinned_to_third_grid_column(self):
        css = (Path(settings.BASE_DIR) / 'bookings/static/bookings/karlak_footer_right_v160.css').read_text()
        self.assertIn('grid-column: 3;', css)
        self.assertIn('justify-self: end;', css)
        self.assertIn('margin-left: auto;', css)

    def test_footer_contact_is_optional(self):
        source = get_template('bookings/public_footer_v149.html').template.source
        self.assertIn('if PUBLIC149.phone or PUBLIC149.email', source)
        self.assertIn('Footer navigation', source)
