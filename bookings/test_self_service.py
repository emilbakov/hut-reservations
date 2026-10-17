from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import (GuestAccessLink, GuestChangeRequest, Hut, Room,
                     Reservation, ReservationItem)
from .self_service import issue_guest_link

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class GuestSelfServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user("guest_manager", password="pw", is_staff=True)
        self.other_manager = User.objects.create_user("other_manager", password="pw", is_staff=True)
        self.hut = Hut.objects.create(name="Self Service Hut", slug="self-service-hut")
        self.other_hut = Hut.objects.create(name="Private Hut", slug="private-hut")
        self.hut.managers.add(self.manager)
        self.other_hut.managers.add(self.other_manager)
        room = Room.objects.create(hut=self.hut, name="Guest room", capacity=2)
        today = timezone.localdate()
        self.reservation = Reservation.objects.create(
            name="Guest", email="guest@example.com", status=Reservation.Status.CONFIRMED,
            check_in=today + timedelta(days=10), check_out=today + timedelta(days=12))
        ReservationItem.objects.create(reservation=self.reservation, room=room,
                                       beds=1, price_per_night=Decimal("50"))
        self.link = issue_guest_link(self.reservation)
        self.staff_url = reverse("bookings:guest_requests_dashboard")

    def test_link_unguessable_and_stable(self):
        self.assertEqual(self.link, issue_guest_link(self.reservation))
        self.assertGreaterEqual(len(GuestAccessLink.objects.get().token), 40)

    def test_guest_page(self):
        response = self.client.get(self.link)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.reservation.code)

    def test_bad_token_404(self):
        self.assertEqual(self.client.get("/guest/manage/not-a-valid-token/").status_code, 404)

    def test_revoked_token_404(self):
        access = GuestAccessLink.objects.get()
        access.revoked_at = timezone.now()
        access.save()
        self.assertEqual(self.client.get(self.link).status_code, 404)

    def test_guest_change_request_does_not_change_booking(self):
        old_dates = (self.reservation.check_in, self.reservation.check_out)
        response = self.client.post(self.link, {
            "request_type": "change", "requested_check_in": str(old_dates[0] + timedelta(days=1)),
            "requested_check_out": str(old_dates[1] + timedelta(days=1)), "details": "Please change dates"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GuestChangeRequest.objects.count(), 1)
        self.reservation.refresh_from_db()
        self.assertEqual((self.reservation.check_in, self.reservation.check_out), old_dates)

    def test_invalid_dates_rejected(self):
        self.client.post(self.link, {"request_type": "change",
            "requested_check_in": "bad", "requested_check_out": "bad"})
        self.assertEqual(GuestChangeRequest.objects.count(), 0)

    def test_guest_cancellation_is_only_request(self):
        self.client.post(self.link, {"request_type": "cancellation", "details": "Cannot attend"})
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)
        self.assertEqual(GuestChangeRequest.objects.get().request_type, "cancellation")

    def test_duplicate_pending_blocked(self):
        for _ in range(2):
            self.client.post(self.link, {"request_type": "cancellation"})
        self.assertEqual(GuestChangeRequest.objects.count(), 1)

    def test_manager_can_approve_without_modifying_reservation(self):
        self.client.post(self.link, {"request_type": "cancellation"})
        self.client.force_login(self.manager)
        change = GuestChangeRequest.objects.get()
        response = self.client.post(self.staff_url, {
            "request_id": change.pk, "decision": "approved", "manager_note": "Review needed"})
        self.assertEqual(response.status_code, 302)
        change.refresh_from_db()
        self.assertEqual(change.status, "approved")
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.CONFIRMED)

    def test_other_manager_cannot_approve(self):
        self.client.post(self.link, {"request_type": "cancellation"})
        self.client.force_login(self.other_manager)
        response = self.client.post(self.staff_url, {
            "request_id": GuestChangeRequest.objects.get().pk, "decision": "approved"})
        self.assertEqual(response.status_code, 404)

    def test_approved_request_cannot_be_reviewed_again(self):
        self.client.post(self.link, {"request_type": "cancellation"})
        self.client.force_login(self.manager)
        change = GuestChangeRequest.objects.get()
        self.client.post(self.staff_url, {"request_id": change.pk, "decision": "approved"})
        self.client.post(self.staff_url, {"request_id": change.pk, "decision": "rejected"})
        change.refresh_from_db()
        self.assertEqual(change.status, "approved")
