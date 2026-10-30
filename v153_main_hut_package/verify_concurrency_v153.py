#!/usr/bin/env python3
"""Exercise shared quotas with real parallel connections to a temporary DB.

Always configures a new local SQLite file. Never connects to the production DB.
Run beside manage.py, or pass --project /path/to/an/isolated/source/check-out.
"""
import argparse
import importlib
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    args = parser.parse_args()
    project = args.project.resolve()
    if not (project / "manage.py").is_file():
        parser.error("Run beside manage.py or pass --project to a source directory.")
    sys.path.insert(0, str(project))
    base = importlib.import_module("config.settings_v145_test")
    values = {key: getattr(base, key) for key in dir(base) if key.isupper()}
    with tempfile.TemporaryDirectory(prefix="summitdesk-v152-concurrency-") as directory:
        values["DATABASES"] = {"default": {"ENGINE": "django.db.backends.sqlite3",
            "NAME": str(Path(directory) / "isolated.sqlite3"),
            "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 30}}}
        from django.conf import settings
        settings.configure(**values)
        import django
        django.setup()
        from django.core.management import call_command
        from django.db import close_old_connections, connections
        from django.http import HttpResponse
        from django.test import RequestFactory, override_settings
        from bookings.booking_guard_v150 import BookingRateLimited, reserve_budget
        from bookings.login_guard_v151 import LoginThrottleMiddleware
        from bookings.models import LoginThrottleBucket, PublicBookingRateBucket

        call_command("migrate", interactive=False, verbosity=0)
        fixed = datetime(2026, 10, 23, 12, 1, tzinfo=timezone.utc)
        gate = threading.Event()
        state_lock = threading.Lock()
        entered, denied = [], []
        barrier = threading.Barrier(8, timeout=20)

        def login_worker(index):
            close_old_connections()
            request = RequestFactory().post("/staff/login/", {"username": "shared-user"}, REMOTE_ADDR="203.0.113.10")
            request.session = {}

            def downstream(req):
                limited = middleware.process_view(req, None, (), {})
                if limited is not None:
                    with state_lock:
                        denied.append(index)
                        if len(denied) == 3:
                            gate.set()
                    return limited
                with state_lock:
                    entered.append(index)
                if not gate.wait(timeout=20):
                    raise AssertionError("Concurrent excess attempts were not rejected before password checks finished")
                req._sd151_login_outcome = "failure"
                return HttpResponse("invalid credentials", status=200)

            middleware = LoginThrottleMiddleware(downstream)
            try:
                barrier.wait()
                return middleware(request).status_code
            finally:
                connections["default"].close()

        with override_settings(LOGIN_PAIR_LIMIT=5, LOGIN_IP_LIMIT=20, LOGIN_ACCOUNT_LIMIT=20,
                               LOGIN_BROWSER_LIMIT=20, TRUST_UNIX_PROXY=False, TRUSTED_PROXY_CIDRS=()), patch(
                "bookings.login_guard_v151.current_time", return_value=fixed):
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(login_worker, index) for index in range(8)]
                results = [future.result(timeout=45) for future in futures]
        assert results.count(200) == 5 and results.count(429) == 3, results
        assert len(entered) == 5 and len(denied) == 3
        assert not LoginThrottleBucket.objects.filter(pending__gt=0).exists()
        failures = sorted(LoginThrottleBucket.objects.values_list("failures", flat=True))
        assert failures == [1, 1, 1, 1, 1, 5, 5, 5], failures
        print("Login burst: 8 parallel requests; 5 password checks admitted, 3 rejected in advance; no pending slots leaked.")

        barrier = threading.Barrier(8, timeout=20)

        def booking_worker(index):
            close_old_connections()
            request = RequestFactory().post("/huts/test/", REMOTE_ADDR=f"203.0.113.{index+20}")
            request.session = {}
            try:
                barrier.wait()
                try:
                    reserve_budget(request, "shared@example.com")
                    return "accepted"
                except BookingRateLimited:
                    return "limited"
            finally:
                connections["default"].close()

        with override_settings(BOOKING_EMAIL_LIMIT=3, BOOKING_IP_LIMIT=60, BOOKING_BROWSER_LIMIT=12), patch(
                "bookings.booking_guard_v150.timezone.now", return_value=fixed):
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(booking_worker, index) for index in range(8)]
                results = [future.result(timeout=45) for future in futures]
        assert results.count("accepted") == 3 and results.count("limited") == 5, results
        assert sorted(PublicBookingRateBucket.objects.values_list("attempts", flat=True)) == [1, 1, 1, 1, 1, 1, 3]
        print("Booking burst: 8 parallel requests; 3 shared-email slots admitted, 5 rejected; no counter updates lost.")
        # Four undo requests compete with four new bookings for one released bed.
        from datetime import timedelta
        from django.contrib.auth import get_user_model
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.utils import timezone as django_timezone
        from bookings.models import Hut, Room, Reservation, ReservationItem
        from bookings.services import create_reservation, NotAvailable
        from bookings.staff_decisions_v152 import decide, undo_decision
        user = get_user_model().objects.create_user('concurrency-manager', is_staff=True)
        hut = Hut.objects.create(name='Concurrent hut', slug='concurrent-hut')
        hut.managers.add(user)
        room = Room.objects.create(hut=hut, name='Last bed', capacity=1)
        first = django_timezone.localdate()+timedelta(days=3)
        original = create_reservation(check_in=first, check_out=first+timedelta(days=2),
            beds_by_room={room.pk:1}, status='pending', name='Original')

        def staff_request(data):
            request = RequestFactory().post('/staff/reservations/action/', data)
            request.user = user
            request.session = {}
            request._messages = FallbackStorage(request)
            return request

        decide(staff_request({'action':'cancel'}), original.code)
        decision = original.staff_decisions.get()
        barrier = threading.Barrier(8, timeout=20)

        def undo_or_book(index):
            close_old_connections()
            try:
                barrier.wait()
                if index < 4:
                    undo_decision(staff_request({}), original.code, decision.pk)
                    return 'undo-request'
                try:
                    create_reservation(check_in=first, check_out=first+timedelta(days=2),
                        beds_by_room={room.pk:1}, status='confirmed', name='Concurrent guest')
                    return 'booked'
                except NotAvailable:
                    return 'unavailable'
            finally:
                connections['default'].close()

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(undo_or_book, index) for index in range(8)]
            results = [future.result(timeout=45) for future in futures]
        decision.refresh_from_db()
        assert int(decision.undone_at is not None) + results.count('booked') == 1, results
        assert sum(ReservationItem.objects.filter(room=room, reservation__status__in=Reservation.HOLDING)
                   .values_list('beds', flat=True)) == 1
        print('Decision race: 4 undo requests and 4 new bookings competed for one released bed; exactly one hold remained, with no overbooking.')
        connections.close_all()
    print("Concurrent quota checks passed using independent connections to a temporary file-backed SQLite database.")


if __name__ == "__main__":
    main()
