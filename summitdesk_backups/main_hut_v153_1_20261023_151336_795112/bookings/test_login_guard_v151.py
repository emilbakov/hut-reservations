"""Real sign-in, trusted transport and in-flight quota regression coverage."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.http import HttpResponseRedirect
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from .client_identity_v151 import client_ip
from .login_guard_v151 import (LoginLimited, LoginThrottleMiddleware, finish_login, reserve_login)
from .models import LoginThrottleBucket, PublicBookingRateBucket
from .booking_guard_v150 import BookingRateLimited, reserve_budget


class ClientIdentityV151Tests(TestCase):
    def request(self, peer="", **headers):
        return RequestFactory().get("/", REMOTE_ADDR=peer, **headers)

    @override_settings(TRUST_UNIX_PROXY=False, TRUSTED_PROXY_CIDRS=())
    def test_direct_peer_ignores_all_forwarded_headers_and_legacy_global_flag(self):
        with override_settings(BEHIND_PROXY=True):
            self.assertEqual(client_ip(self.request("203.0.113.50", HTTP_X_REAL_IP="198.51.100.5", HTTP_X_FORWARDED_FOR="198.51.100.6")), "203.0.113.50")

    @override_settings(TRUST_UNIX_PROXY=False, TRUSTED_PROXY_CIDRS=())
    def test_unconfigured_unix_and_loopback_peers_have_no_shared_identity(self):
        for peer in ("", "127.0.0.1", "::1", "garbage"):
            self.assertIsNone(client_ip(self.request(peer, HTTP_X_REAL_IP="198.51.100.7")))

    @override_settings(TRUST_UNIX_PROXY=True, TRUSTED_PROXY_CIDRS=())
    def test_explicit_unix_trust_reads_only_a_valid_single_x_real_ip(self):
        self.assertEqual(client_ip(self.request(HTTP_X_REAL_IP="198.51.100.7", HTTP_X_FORWARDED_FOR="forged")), "198.51.100.7")
        for value in ("", "unknown", "1.2.3.4, 5.6.7.8", "::1", "0.0.0.0", "fe80::1%eth0"):
            self.assertIsNone(client_ip(self.request(HTTP_X_REAL_IP=value)))
        self.assertIsNone(client_ip(self.request(HTTP_X_FORWARDED_FOR="198.51.100.8")))

    @override_settings(TRUST_UNIX_PROXY=True, TRUSTED_PROXY_CIDRS=("10.0.0.4/32",))
    def test_unix_trust_does_not_enable_forwarding_from_an_arbitrary_tcp_peer(self):
        self.assertEqual(client_ip(self.request("203.0.113.3", HTTP_X_REAL_IP="198.51.100.4")), "203.0.113.3")
        self.assertEqual(client_ip(self.request("10.0.0.4", HTTP_X_REAL_IP="198.51.100.4")), "198.51.100.4")
        self.assertIsNone(client_ip(self.request("10.0.0.4")))

    @override_settings(TRUSTED_PROXY_CIDRS=())
    def test_equivalent_ipv6_and_mapped_ipv4_addresses_are_normalized(self):
        self.assertEqual(client_ip(self.request("2001:0db8:0000:0000:0000:0000:0000:0001")), "2001:db8::1")
        self.assertEqual(client_ip(self.request("::ffff:203.0.113.4")), "203.0.113.4")

    @override_settings(TRUST_UNIX_PROXY=True, BOOKING_IP_LIMIT=1)
    def test_booking_guard_reuses_the_same_trust_contract_without_a_second_limiter(self):
        one = self.request(HTTP_X_REAL_IP="198.51.100.9");one.session = {}
        reserve_budget(one, "one@example.com")
        two = self.request(HTTP_X_REAL_IP="198.51.100.9");two.session = {}
        with self.assertRaises(BookingRateLimited):
            reserve_budget(two, "two@example.com")
        self.assertEqual(PublicBookingRateBucket.objects.count(), 3)


@override_settings(TRUST_UNIX_PROXY=False, TRUSTED_PROXY_CIDRS=())
class LoginGuardV151Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("boss", "boss@example.com", "right-password")
        self.url = reverse("bookings:staff_login")

    def attempt(self, client=None, username="boss", password="wrong", peer="203.0.113.10", url=None, **headers):
        return (client or self.client).post(url or self.url, {"username": username, "password": password}, REMOTE_ADDR=peer, **headers)

    def test_five_failures_stop_password_verification_and_return_uncached_retry_response(self):
        for _ in range(5):
            self.assertEqual(self.attempt().status_code, 200)
        with patch("django.contrib.auth.forms.authenticate") as authenticate:
            response = self.attempt(password="right-password")
        self.assertEqual(response.status_code, 429)
        authenticate.assert_not_called()
        self.assertTrue(1 <= int(response["Retry-After"]) <= 900)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "A password reset does not clear", status_code=429)
        self.assertFalse(LoginThrottleBucket.objects.filter(pending__gt=0).exists())

    def test_another_ip_can_login_after_the_first_pair_is_limited(self):
        for _ in range(5):
            self.attempt()
        response = self.attempt(client=Client(), peer="203.0.113.11", password="right-password")
        self.assertEqual(response.status_code, 302)

    def test_valid_login_resets_pair_failures_and_retains_existing_auth_permissions(self):
        for _ in range(4):
            self.attempt()
        self.assertEqual(self.attempt(password="right-password").status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.client.logout()
        for _ in range(4):
            self.assertEqual(self.attempt().status_code, 200)
        regular = get_user_model().objects.create_user("no-role", password="right-password")
        response = self.attempt(username=regular.username, password="right-password", peer="203.0.113.12")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_and_staff_login_share_attempt_budgets(self):
        for _ in range(5):
            self.assertEqual(self.attempt(url="/admin/login/").status_code, 200)
        self.assertEqual(self.attempt().status_code, 429)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)

    def test_ip_budget_spans_usernames_and_clients(self):
        for index in range(20):
            self.assertEqual(self.attempt(client=Client(), username=f"missing-{index}").status_code, 200)
        self.assertEqual(self.attempt(client=Client(), username="different").status_code, 429)

    def test_missing_unix_address_does_not_lock_out_other_browsers_site_wide(self):
        first, second = Client(), Client()
        for index in range(20):
            self.assertEqual(self.attempt(client=first, username=f"missing-{index}", peer="", HTTP_X_REAL_IP="198.51.100.8").status_code, 200)
        self.assertEqual(self.attempt(client=first, username="another", peer="").status_code, 429)
        response = self.attempt(client=second, peer="", password="right-password", HTTP_X_REAL_IP="198.51.100.9")
        self.assertEqual(response.status_code, 302)

    def test_account_budget_spans_browsers_and_addresses(self):
        for index in range(20):
            self.assertEqual(self.attempt(client=Client(), peer=f"203.0.113.{index+20}").status_code, 200)
        self.assertEqual(self.attempt(client=Client(), peer="203.0.113.99", password="right-password").status_code, 429)
        self.assertEqual(self.attempt(client=Client(), peer="203.0.113.99", username="unrelated").status_code, 200)

    @override_settings(TRUST_UNIX_PROXY=True)
    def test_trusted_unix_proxy_separates_clients_by_real_ip(self):
        for _ in range(5):
            self.attempt(peer="", HTTP_X_REAL_IP="198.51.100.10")
        self.assertEqual(self.attempt(peer="", password="right-password", HTTP_X_REAL_IP="198.51.100.10").status_code, 429)
        self.assertEqual(self.attempt(client=Client(), peer="", password="right-password", HTTP_X_REAL_IP="198.51.100.11").status_code, 302)

    def test_rejected_csrf_request_and_get_do_not_create_counter_rows(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.attempt(client=client).status_code, 403)
        self.client.get(self.url)
        self.assertFalse(LoginThrottleBucket.objects.exists())

    def test_database_failure_stops_authentication_with_503(self):
        with patch("bookings.login_guard_v151.reserve_login", side_effect=OperationalError("unavailable")), patch("django.contrib.auth.forms.authenticate") as authenticate:
            response = self.attempt(password="right-password")
        self.assertEqual(response.status_code, 503)
        authenticate.assert_not_called()
        self.assertContains(response, "Sign-in temporarily unavailable", status_code=503)

    def test_bulgarian_block_page_and_actual_window_retry(self):
        self.client.cookies["django_language"] = "bg"
        start = datetime(2026, 10, 23, 12, 14, 30, tzinfo=dt_timezone.utc)
        with patch("bookings.login_guard_v151.current_time", return_value=start):
            for _ in range(5):
                self.attempt()
            response = self.attempt()
        self.assertEqual(response["Retry-After"], "30")
        self.assertContains(response, "Твърде много опити за вход", status_code=429)
        with patch("bookings.login_guard_v151.current_time", return_value=start + timedelta(seconds=31)):
            self.assertEqual(self.attempt(password="right-password").status_code, 302)

    def test_in_flight_attempts_consume_slots_before_password_checks_complete(self):
        request = RequestFactory().post(self.url, {"username": "boss"}, REMOTE_ADDR="203.0.113.10")
        request.session = {}
        reservations = [reserve_login(request) for _ in range(5)]
        with self.assertRaises(LoginLimited):
            reserve_login(request)
        pair = LoginThrottleBucket.objects.get(pk=reservations[0].pair_key)
        self.assertEqual((pair.failures, pair.pending), (0, 5))
        finish_login(reservations[0], "success")
        for reservation in reservations[1:]:
            finish_login(reservation, "failure")
        pair.refresh_from_db()
        self.assertEqual((pair.failures, pair.pending), (4, 0))
        self.assertFalse(LoginThrottleBucket.objects.filter(pending__gt=0).exists())

    def test_only_auth_signals_can_reset_failures_not_an_arbitrary_redirect(self):
        request = RequestFactory().post(self.url, {"username": "boss"}, REMOTE_ADDR="203.0.113.10")
        request.session = {}
        first = reserve_login(request);finish_login(first, "failure")
        middleware = LoginThrottleMiddleware(lambda r: HttpResponseRedirect("/"))
        middleware.process_view(request, None, (), {})
        middleware(request)
        pair = LoginThrottleBucket.objects.get(pk=first.pair_key)
        self.assertEqual((pair.failures, pair.pending), (1, 0))

    def test_completed_windows_are_pruned_and_keys_expose_no_raw_credentials(self):
        request = RequestFactory().post(self.url, {"username": "boss"}, REMOTE_ADDR="203.0.113.10")
        request.session = {}
        now = datetime(2026, 10, 23, 12, 1, tzinfo=dt_timezone.utc)
        with patch("bookings.login_guard_v151.current_time", return_value=now):
            reserved = reserve_login(request);finish_login(reserved, "failure")
        self.assertEqual(LoginThrottleBucket.objects.count(), 4)
        with patch("bookings.login_guard_v151.current_time", return_value=now + timedelta(hours=1)):
            reserved = reserve_login(request);finish_login(reserved, "failure")
        self.assertEqual(LoginThrottleBucket.objects.count(), 4)
        for key in LoginThrottleBucket.objects.values_list("pk", flat=True):
            self.assertEqual(len(key), 64)
            self.assertNotIn("boss", key)
            self.assertNotIn("203.0.113", key)

    def test_ipv6_pair_keys_cannot_collide_with_colons_in_submitted_usernames(self):
        first = RequestFactory().post(self.url, {"username": "a:b"}, REMOTE_ADDR="2001:db8::1")
        second = RequestFactory().post(self.url, {"username": "b"}, REMOTE_ADDR="2001:db8::1:a")
        first.session = {}; second.session = {}
        one, two = reserve_login(first), reserve_login(second)
        self.assertNotEqual(one.pair_key, two.pair_key)
        finish_login(one, "failure"); finish_login(two, "failure")
