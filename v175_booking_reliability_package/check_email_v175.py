#!/usr/bin/env python3
"""Read configuration/queue totals and optionally open SMTP, without sending mail."""
import argparse
import os
from pathlib import Path
import sys


def configuration_issues(settings):
    issues = []
    if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
        issues.append('EMAIL_BACKEND is not the SMTP backend.')
    if not settings.EMAIL_HOST:
        issues.append('EMAIL_HOST is empty.')
    try:
        port = int(settings.EMAIL_PORT)
        if not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        issues.append('EMAIL_PORT must be between 1 and 65535.')
    if settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL:
        issues.append('EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be enabled.')
    if bool(settings.EMAIL_HOST_USER) != bool(settings.EMAIL_HOST_PASSWORD):
        issues.append('SMTP username and password must be configured together.')
    if (settings.EMAIL_HOST_USER or settings.EMAIL_HOST_PASSWORD) and not (
            settings.EMAIL_USE_TLS or settings.EMAIL_USE_SSL):
        issues.append('Enable EMAIL_USE_TLS or EMAIL_USE_SSL before SMTP authentication.')
    if str(settings.EMAIL_HOST).lower() == 'smtp.gmail.com' and not (
            settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD):
        issues.append('Gmail SMTP requires the configured account and app password.')
    if settings.DEBUG:
        issues.append('Production DJANGO_DEBUG is enabled.')
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connect', action='store_true',
                        help='Open/authenticate and close SMTP; never send a message.')
    args = parser.parse_args(argv)
    root = Path.cwd().resolve()
    if not (root / 'manage.py').is_file():
        print('Run from the project directory beside manage.py.')
        return 1
    sys.path.insert(0, str(root))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_postgres')
    import django
    django.setup()
    from django.conf import settings
    from django.db.models import Count
    from django.utils import timezone
    from bookings.models import ReservationNotification
    from bookings.notifications_v145 import MAX_ATTEMPTS

    issues = configuration_issues(settings)
    for issue in issues:
        print('Configuration issue: ' + issue)
    if not issues:
        print('SMTP configuration: OK. No account names or secrets are printed.')
    counts = {row['status']: row['count'] for row in
              ReservationNotification.objects.values('status').annotate(count=Count('pk'))}
    print('Notification queue: ' + ', '.join(
        f'{status}={counts.get(status, 0)}' for status in ['pending', 'failed', 'sent', 'skipped']))
    due = ReservationNotification.objects.filter(status__in=['pending', 'failed'],
        attempts__lt=MAX_ATTEMPTS, next_attempt_at__lte=timezone.now()).count()
    print(f'Notifications currently due for retry: {due}. No retries were executed.')
    if issues:
        return 1
    if not args.connect:
        print('Connection not tested. Add --connect for a no-message SMTP connection check.')
        return 0
    from django.core.mail import get_connection
    connection = get_connection(fail_silently=False)
    try:
        connection.open()
    except Exception as exc:
        # Raw SMTP exceptions may contain credentials or server-provided content.
        print(f'SMTP connection/authentication failed ({type(exc).__name__}). Check the existing server email settings.')
        return 1
    finally:
        try:
            connection.close()
        except Exception:
            pass
    print('SMTP connection/authentication: OK. No email was sent.')
    print('Inbox delivery and spam-folder placement still require a controlled live message.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'Email diagnostic could not complete ({type(exc).__name__}). No secret values were printed.')
        raise SystemExit(1)
