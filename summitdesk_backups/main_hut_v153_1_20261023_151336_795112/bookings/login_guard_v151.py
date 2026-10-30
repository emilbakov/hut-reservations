"""Atomically reserve login slots before password verification, across workers."""
import json
import logging
import math
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db import DatabaseError, transaction
from django.shortcuts import render
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .client_identity_v151 import client_ip
from .models import LoginThrottleBucket
from .reliability_v145 import browser_secret

logger = logging.getLogger(__name__)
LOGIN_PATHS = {"/staff/login/", "/admin/login/"}
WINDOW = 15 * 60


def current_time():
    return timezone.now()


class LoginLimited(Exception):
    def __init__(self, retry_after):
        self.retry_after = max(1, retry_after)


@dataclass(frozen=True)
class LoginReservation:
    keys: tuple
    pair_key: str


def _key(kind, value, period):
    encoded = json.dumps([kind, value, period], separators=(",", ":"), ensure_ascii=True)
    return salted_hmac("summitdesk.login-budget.v151", encoded, algorithm="sha256").hexdigest()


def reserve_login(request):
    now = current_time()
    period = int(now.timestamp()) // WINDOW
    expires = datetime.fromtimestamp((period + 1) * WINDOW, tz=datetime_timezone.utc)
    username = unicodedata.normalize("NFKC", request.POST.get("username", "")).strip().casefold()
    browser = browser_secret(request)
    peer = client_ip(request)
    identity = ("ip", peer) if peer else ("browser", browser)
    pair = _key("pair", (identity, username), period)
    budgets = [
        (pair, settings.LOGIN_PAIR_LIMIT),
        (_key("browser", browser, period), settings.LOGIN_BROWSER_LIMIT),
        (_key("account", username, period), settings.LOGIN_ACCOUNT_LIMIT),
    ]
    if peer:
        budgets.append((_key("peer", peer, period), settings.LOGIN_IP_LIMIT))
    with transaction.atomic():
        locked = []
        for key, limit in sorted(budgets):
            LoginThrottleBucket.objects.get_or_create(key=key, defaults={"expires_at": expires})
            bucket = LoginThrottleBucket.objects.select_for_update().get(pk=key)
            if bucket.failures + bucket.pending >= limit:
                raise LoginLimited(math.ceil((expires - now).total_seconds()))
            locked.append(bucket)
        for bucket in locked:
            bucket.pending += 1
            bucket.save(update_fields=["pending"])
        stale = list(LoginThrottleBucket.objects.filter(expires_at__lte=now).values_list("pk", flat=True)[:100])
        if stale:
            LoginThrottleBucket.objects.filter(pk__in=stale).delete()
    return LoginReservation(tuple(key for key, _ in budgets), pair)


def finish_login(reservation, outcome):
    with transaction.atomic():
        # Successful authentication clears the pair's failures, never another
        # request's in-flight slot or the aggregate IP/browser/account failures.
        for key in sorted(reservation.keys):
            bucket = LoginThrottleBucket.objects.select_for_update().filter(pk=key).first()
            if bucket is None:
                continue  # Its fixed window already expired and was pruned.
            bucket.pending = max(0, bucket.pending - 1)
            if outcome == "failure":
                bucket.failures += 1
            elif outcome == "success" and key == reservation.pair_key:
                bucket.failures = 0
            bucket.save(update_fields=["pending", "failures"])


def _login_succeeded(sender, request, **kwargs):
    if request is not None and hasattr(request, "_sd151_login_reservation"):
        request._sd151_login_outcome = "success"


def _login_failed(sender, request=None, **kwargs):
    if request is not None and hasattr(request, "_sd151_login_reservation"):
        request._sd151_login_outcome = "failure"


def register_signals():
    user_logged_in.connect(_login_succeeded, dispatch_uid="sd151_login_success", weak=False)
    user_login_failed.connect(_login_failed, dispatch_uid="sd151_login_failure", weak=False)


def _response(request, status, seconds=None):
    response = render(request, "bookings/login_limited_v151.html", {
        "login_unavailable": status == 503,
        "retry_minutes": max(1, math.ceil(seconds / 60)) if seconds else 1,
        "login_path": request.path,
    }, status=status)
    response["Cache-Control"] = "no-store, max-age=0"
    response["Pragma"] = "no-cache"
    if seconds:
        response["Retry-After"] = str(seconds)
    return response


class LoginThrottleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Listed after CsrfViewMiddleware: rejected CSRF submissions reach
        # neither password verification nor the database reservation below.
        if request.method != "POST" or request.path_info not in LOGIN_PATHS:
            return None
        try:
            reservation = reserve_login(request)
        except LoginLimited as exc:
            return _response(request, 429, exc.retry_after)
        except DatabaseError:
            logger.error("Login protection database unavailable; authentication was not attempted.")
            return _response(request, 503, 60)
        request._sd151_login_reservation = reservation
        return None

    def __call__(self, request):
        if request.method != "POST" or request.path_info not in LOGIN_PATHS:
            return self.get_response(request)
        outcome = None
        try:
            response = self.get_response(request)
            outcome = getattr(request, "_sd151_login_outcome", None)
            # Missing fields/role denial render an invalid form without emitting
            # a failed-auth signal. CSRF/other error responses release the slot.
            form = (getattr(response, "context_data", None) or {}).get("form")
            if outcome is None and response.status_code == 200 and form is not None and form.errors:
                outcome = "failure"
        finally:
            reservation = getattr(request, "_sd151_login_reservation", None)
            if reservation is not None:
                outcome = outcome or getattr(request, "_sd151_login_outcome", None)
                try:
                    finish_login(reservation, outcome)
                except DatabaseError:
                    logger.error("Could not finalize login protection counters.")
        return response
