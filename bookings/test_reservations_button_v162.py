"""Regression coverage for action button contrast on staff reservations."""
from django.test import SimpleTestCase
from django.template.loader import get_template


class ReservationActionButtonContrastV162Tests(SimpleTestCase):
    def test_cancel_button_keeps_visible_label_and_safe_post(self):
        html = get_template("bookings/manager_reservations.html").template.source
        self.assertIn('class="sd152-danger"', html)
        self.assertIn('name="action" value="cancel"', html)
        self.assertIn('name="reason"', html)
        self.assertIn('{% csrf_token %}', html)

    def test_danger_button_has_contrasting_background_and_text(self):
        html = get_template("bookings/manager_reservations.html").template.source
        self.assertIn('.mr-page .mr-actions button.sd152-danger{background:#a43432!important;', html)
        self.assertIn('color:#fff!important}', html)
        self.assertIn('.mr-page .mr-actions button.sd152-danger:hover', html)

    def test_approval_button_retains_green_background(self):
        html = get_template("bookings/manager_reservations.html").template.source
        self.assertIn('.mr-page .mr-actions button.sd152-button{background:#195b42!important;', html)
