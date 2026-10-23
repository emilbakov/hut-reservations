"""Guest error recovery, honest receipts and shared anti-abuse budgets."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .booking_guard_v150 import BookingRateLimited, reserve_budget
from .models import (Hut, Room, Reservation, PublicBookingRateBucket,
                     ReservationNotification, GuestChangeRequest, PublicWebsiteSettings)
from .self_service import issue_guest_link
from .services import create_reservation


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", BOOKING_NOTIFY_EMAIL="")
class GuestBookingFlowV150Tests(TestCase):
    def setUp(self):
        self.hut = Hut.objects.create(name="Musala Hut", slug="musala-hut", location="Rila Mountains",
            public_phone="+359 888 123 456", public_email="keeper@example.com", directions_url="https://www.openstreetmap.org/",
            reply_time_en="We reply during staffed reception hours.", reply_time_bg="Отговаряме в работното време на рецепцията.",
            payment_instructions_en="Pay the agreed deposit by bank transfer after approval.", payment_instructions_bg="Плати уговорения депозит по банков път след одобрение.")
        self.room = Room.objects.create(hut=self.hut, name="Dorm", capacity=20, price_per_night="18.00")
        self.url = reverse("bookings:hut_detail", args=[self.hut.slug])
        self.start = timezone.localdate() + timedelta(days=9)

    def payload(self, **extra):
        return {"check_in": self.start.isoformat(), "check_out": (self.start + timedelta(days=2)).isoformat(),
            "name": "Ana Guest", "email": "ana@example.com", "phone": "", "notes": "Late arrival", "beds": "2",
            f"room_{self.room.pk}": "2", **extra}

    def post(self, client=None, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            return (client or self.client).post(self.url, self.payload(**extra))

    def receipt(self):
        response = self.post()
        self.assertEqual(response.status_code, 302)
        return self.client.get(response.url)

    def test_contact_and_zero_bed_errors_are_reported_together_with_values_kept(self):
        response = self.post(email="bad-email", **{f"room_{self.room.pk}": "0"})
        self.assertContains(response, "Enter a valid email address.")
        self.assertContains(response, "Choose at least one bed.")
        self.assertContains(response, 'id="sd150-errors"')
        self.assertContains(response, 'href="#id_email"')
        self.assertContains(response, 'href="#rooms"')
        self.assertContains(response, 'value="bad-email"')
        self.assertContains(response, 'value="Ana Guest"')
        self.assertContains(response, "Late arrival")
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(PublicBookingRateBucket.objects.exists())

    def test_group_mismatch_is_not_hidden_by_a_contact_error(self):
        response = self.post(email="bad-email", **{f"room_{self.room.pk}": "1"})
        self.assertContains(response, "Enter a valid email address.")
        self.assertContains(response, "Select exactly 2 beds")

    def test_invalid_room_count_has_a_linked_error_without_misleading_zero_beds_error(self):
        response = self.post(email="bad-email", **{f"room_{self.room.pk}": "-1"})
        self.assertContains(response, f'href="#id_room_{self.room.pk}"')
        self.assertContains(response, "Enter a valid email address.")
        self.assertNotContains(response, "Choose at least one bed.")

    def test_date_and_party_errors_have_top_summary(self):
        response = self.client.get(self.url, {"check_in": self.start.isoformat(), "check_out": self.start.isoformat(), "beds": "99"})
        self.assertContains(response, "Departure must be after arrival.")
        self.assertContains(response, "Choose between 1 and 30 guests.")
        self.assertContains(response, 'href="#id_check_out"')
        self.assertContains(response, 'href="#ph-search-guests"')

    def test_required_labels_autofill_phone_explanation_and_empty_total(self):
        response = self.client.get(self.url, self.payload())
        self.assertContains(response, 'autocomplete="name"')
        self.assertContains(response, 'autocomplete="email"')
        self.assertContains(response, 'autocomplete="tel"')
        self.assertContains(response, 'inputmode="tel"')
        self.assertContains(response, 'type="tel"')
        self.assertContains(response, "(required)")
        self.assertContains(response, "(optional)")
        self.assertContains(response, "Helps the hut contact you about arrival changes.")
        self.assertContains(response, "Choose beds to see the total")
        self.assertContains(response, 'id="ph-total-value" hidden')
        self.assertContains(response, "novalidate")
        self.assertContains(response, "#sd150-errors")

    def test_phone_stays_optional_and_pending_receipt_has_hut_contact_next_steps_and_payment(self):
        response = self.receipt()
        self.assertContains(response, "Request received.")
        self.assertNotContains(response, "Your adventure awaits.")
        self.assertContains(response, "Estimated total")
        self.assertContains(response, "72.00")
        self.assertContains(response, "Musala Hut")
        self.assertContains(response, "Rila Mountains")
        self.assertContains(response, 'href="tel:+359888123456"')
        self.assertContains(response, 'mailto:keeper@example.com')
        self.assertContains(response, "Location and directions")
        self.assertContains(response, "What happens next?")
        self.assertContains(response, self.hut.reply_time_en)
        self.assertContains(response, self.hut.payment_instructions_en)
        self.assertTemplateUsed(response, "bookings/public_base_v124.html")
        self.assertIn("no-store", response["Cache-Control"])

    def test_guest_email_contains_same_hut_information_and_correct_request_link_wording(self):
        self.post()
        body = mail.outbox[0].body
        self.assertIn("Musala Hut", body)
        self.assertIn(self.hut.public_phone, body)
        self.assertIn(self.hut.directions_url, body)
        self.assertIn(self.hut.payment_instructions_en, body)
        self.assertIn(self.hut.reply_time_en, body)
        self.assertIn("ask for changes", body)
        self.assertNotIn("or cancel it using", body)

    def test_plain_fallbacks_do_not_invent_payment_methods_or_reply_deadlines(self):
        self.hut.public_phone = self.hut.public_email = self.hut.directions_url = ""
        self.hut.reply_time_en = self.hut.reply_time_bg = ""
        self.hut.payment_instructions_en = self.hut.payment_instructions_bg = ""
        self.hut.save()
        response = self.receipt()
        self.assertContains(response, "No payment is collected by this booking request form.")
        self.assertContains(response, "The hut manager will email their decision.")
        self.assertNotContains(response, "bank transfer")
        self.assertNotContains(response, "24 hours")

    def test_owner_hut_wording_is_escaped(self):
        self.hut.payment_instructions_en = '<script>alert("bad")</script>'
        self.hut.save()
        response = self.receipt()
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("bad")</script>')

    def test_started_and_cancelled_stays_have_no_guest_change_or_cancel_actions(self):
        self.receipt()
        reservation = Reservation.objects.get()
        for offset, status in [(0, "pending"), (-1, "confirmed"), (8, "cancelled")]:
            with self.subTest(offset=offset, status=status):
                Reservation.objects.filter(pk=reservation.pk).update(check_in=timezone.localdate() + timedelta(days=offset), status=status)
                reservation.refresh_from_db()
                response = self.client.get(reservation.get_absolute_url())
                self.assertNotContains(response, "Request a change or cancellation")
                self.assertNotContains(response, 'action="' + reverse("bookings:cancel", args=[reservation.code]) + '"')
                portal = issue_guest_link(reservation)
                self.assertNotContains(self.client.get(portal), 'id="gss-request-form"')
                self.client.post(portal, {"request_type": "cancellation"})
                self.assertFalse(GuestChangeRequest.objects.exists())

    def test_future_guest_actions_and_authorized_staff_tools_are_preserved(self):
        response = self.receipt()
        self.assertContains(response, "Request a change or cancellation")
        reservation = Reservation.objects.get()
        staff = get_user_model().objects.create_superuser("flow-admin", "admin@example.com", "test")
        self.client.force_login(staff)
        response = self.client.get(reservation.get_absolute_url())
        self.assertContains(response, "Cancel reservation")
        self.assertTemplateUsed(response, "bookings/public_base_v124.html")
        self.assertNotContains(response, 'class="site-header adventure-header"')
        self.assertContains(response, 'class="pub-header"')
        self.assertContains(response, 'class="pub-nav"')

    def test_privacy_explanation_is_present_without_a_published_policy_and_link_appears_when_published(self):
        response = self.client.get(self.url, self.payload())
        self.assertContains(response, "We use your details to process this request")
        self.assertNotContains(response, reverse("bookings:public_policy", args=["privacy"]))
        PublicWebsiteSettings.objects.create(operator_name="Example Operator", contact_email="privacy@example.com", privacy_en="Reviewed policy", privacy_published=True)
        self.assertContains(self.client.get(self.url, self.payload()), reverse("bookings:public_policy", args=["privacy"]))

    def test_honeypot_blocks_inventory_and_email_writes(self):
        response = self.post(contact_url="https://spam.example/")
        self.assertContains(response, "We couldn&#x27;t verify this request.")
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(ReservationNotification.objects.exists())
        self.assertFalse(PublicBookingRateBucket.objects.exists())
        self.assertFalse(mail.outbox)

    @override_settings(BOOKING_EMAIL_LIMIT=1)
    def test_email_budget_is_shared_by_clients_and_blocked_request_keeps_details(self):
        self.post()
        response = self.post(client=Client(), name="Second Guest")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertContains(response, "Too many booking requests.", status_code=429)
        self.assertContains(response, 'value="Second Guest"', status_code=429)
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(ReservationNotification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(BOOKING_BROWSER_LIMIT=1)
    def test_browser_budget_spans_email_addresses_and_duplicate_retry_does_not_spend_budget(self):
        self.client.get(self.url)
        first = self.post()
        second = self.post()
        self.assertEqual(first.url, second.url)
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        response = self.post(email="other@example.com")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_shared_budget_uses_only_hashed_identifiers_and_expires(self):
        request = RequestFactory().post("/", REMOTE_ADDR="203.0.113.10", HTTP_X_FORWARDED_FOR="198.51.100.8")
        request.session = {}
        now = timezone.now()
        with override_settings(BOOKING_BROWSER_LIMIT=1, BOOKING_EMAIL_LIMIT=1, BOOKING_IP_LIMIT=1), patch("bookings.booking_guard_v150.timezone.now", return_value=now):
            reserve_budget(request, "ANA@example.com")
            self.assertEqual(PublicBookingRateBucket.objects.count(), 3)
            with self.assertRaises(BookingRateLimited):
                reserve_budget(request, "ana@example.com")
        for key in PublicBookingRateBucket.objects.values_list("pk", flat=True):
            self.assertEqual(len(key), 64)
            self.assertNotIn("ana", key)
            self.assertNotIn("203.0.113", key)
        with patch("bookings.booking_guard_v150.timezone.now", return_value=now + timedelta(hours=2)):
            reserve_budget(request, "ana@example.com")
        self.assertEqual(PublicBookingRateBucket.objects.count(), 3)

    @override_settings(BOOKING_IP_LIMIT=1)
    def test_forwarded_headers_cannot_reset_real_peer_budget_and_unix_peers_are_not_shared(self):
        one = RequestFactory().post("/", REMOTE_ADDR="203.0.113.5", HTTP_X_FORWARDED_FOR="192.0.2.1")
        one.session = {}
        reserve_budget(one, "first@example.com")
        two = RequestFactory().post("/", REMOTE_ADDR="203.0.113.5", HTTP_X_FORWARDED_FOR="192.0.2.2")
        two.session = {}
        with self.assertRaises(BookingRateLimited):
            reserve_budget(two, "second@example.com")
        self.assertEqual(PublicBookingRateBucket.objects.count(), 3)  # blocked transaction created no extra buckets
        for index, address in enumerate(("", "127.0.0.1")):
            request = RequestFactory().post("/", REMOTE_ADDR=address)
            request.session = {}
            reserve_budget(request, f"unix-{index}@example.com")

    def test_bulgarian_errors_receipt_and_email(self):
        self.client.cookies["django_language"] = "bg"
        response = self.post(email="invalid", **{f"room_{self.room.pk}": "0"})
        self.assertContains(response, "Провери заявката си")
        response = self.receipt()
        self.assertContains(response, "Заявката е получена.")
        self.assertContains(response, self.hut.payment_instructions_bg)
        self.assertContains(response, self.hut.reply_time_bg)
        self.assertIn("Заявката ти ОЧАКВА ОДОБРЕНИЕ.", mail.outbox[0].body)

    def test_legacy_booking_route_gets_the_same_error_recovery_and_guard(self):
        response = self.client.post(reverse("bookings:book"), self.payload(email="bad", **{f"room_{self.room.pk}": "0"}))
        self.assertContains(response, "Choose at least one bed.")
        self.assertContains(response, "Enter a valid email address.")
        self.assertContains(response, "booking_feedback_v150.js")
        self.assertContains(response, 'name="contact_url"')
        self.assertContains(response, "autocomplete=\"tel\"")

    def test_hut_contact_validation_rejects_script_urls_and_markup(self):
        self.hut.directions_url = "javascript:alert(1)"
        self.hut.public_phone = '<script>alert(1)</script>'
        with self.assertRaises(ValidationError):
            self.hut.full_clean()
