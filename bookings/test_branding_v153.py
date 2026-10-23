"""Regression checks for the Karlak organization brand assets (v153)."""

from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase


class KarlakBrandingTests(SimpleTestCase):
    def test_logo_and_icon_assets_are_available(self):
        for filename in (
            "karlak-logo-dark-v153.png",
            "karlak-logo-light-v153.png",
            "karlak-favicon-v153.png",
            "karlak-apple-touch-v153.png",
        ):
            with self.subTest(filename=filename):
                self.assertTrue((Path(settings.BASE_DIR) / "bookings" / "static" / "bookings" / filename).is_file())

    def test_public_and_staff_brand_templates_compile(self):
        for template in (
            "bookings/public_base_v124.html",
            "bookings/public_footer_v149.html",
            "bookings/public_head_v149.html",
            "bookings/base.html",
            "bookings/staff_login.html",
            "floorplans/includes/summitdesk_nav.html",
        ):
            with self.subTest(template=template):
                self.assertIsNotNone(get_template(template))

    def test_branding_is_shared_across_public_and_staff_shells(self):
        templates = (
            "bookings/public_base_v124.html",
            "bookings/staff_login.html",
            "floorplans/includes/summitdesk_nav.html",
        )
        for template in templates:
            with self.subTest(template=template):
                source = get_template(template).template.source
                self.assertIn("karlak-logo-", source)
