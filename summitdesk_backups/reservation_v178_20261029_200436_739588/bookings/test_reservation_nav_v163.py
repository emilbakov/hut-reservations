"""v163: /r/<code>/ uses the same public Karlak navigation for staff and guests."""
from django.test import SimpleTestCase
from .booking_flow_v150 import receipt_context


class ReservationNavV163Tests(SimpleTestCase):
    def test_receipt_uses_public_navigation_for_staff_and_guests(self):
        class ReservationWithNoItems:
            class Items:
                def all(self):
                    return []
            items = Items()
            status = "cancelled"
            HOLDING = ("pending", "confirmed")
            check_in = None

        reservation = ReservationWithNoItems()
        for staff in (False, True):
            with self.subTest(staff=staff):
                context = receipt_context(reservation, staff=staff)
                self.assertEqual(context["reservation_base_template"], "bookings/public_base_v124.html")
