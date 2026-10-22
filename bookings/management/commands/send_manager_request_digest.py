"""Preview by default. --send delivers a once-daily manager email digest."""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from bookings.manager_digest_v129 import (
    DigestConfigurationError, digest_manager, validated_base_url,
)


class Command(BaseCommand):
    help = 'Preview or send a daily per-manager digest of pending public guest requests.'

    def add_arguments(self, parser):
        parser.add_argument('--send', action='store_true', help='Deliver email (default: preview only).')
        parser.add_argument('--base-url', default=None, help='Trusted HTTPS site origin; overrides SUMMITDESK_BASE_URL.')
        parser.add_argument('--manager-id', type=int, default=None, help='Limit to a single assigned manager account.')

    def handle(self, *args, **options):
        sending = options['send']
        base_url = options['base_url'] if options['base_url'] is not None else os.environ.get('SUMMITDESK_BASE_URL', '')
        if sending:
            try:
                base_url = validated_base_url(base_url)
            except DigestConfigurationError as exc:
                raise CommandError(str(exc)) from exc
            if settings.EMAIL_BACKEND in {
                'django.core.mail.backends.console.EmailBackend',
                'django.core.mail.backends.dummy.EmailBackend',
                'django.core.mail.backends.filebased.EmailBackend',
            }:
                raise CommandError('Configure a real email backend before --send; test/console/file email is not delivered.')
        now = timezone.now()
        User = get_user_model()
        managers = (User.objects.filter(is_active=True, managed_huts__is_active=True)
                    .exclude(email__isnull=True).exclude(email='').distinct().order_by('pk'))
        if options['manager_id'] is not None:
            managers = managers.filter(pk=options['manager_id'])
        counts = {'sent': 0, 'preview': 0, 'duplicate': 0, 'empty': 0, 'disabled': 0, 'not_urgent': 0, 'ineligible': 0, 'failed': 0}
        for manager_id in managers.values_list('pk', flat=True).iterator():
            try:
                result, requests = digest_manager(manager_id, send=sending, base_url=base_url, now=now)
            except Exception as exc:
                counts['failed'] += 1
                self.stderr.write(f'Manager {manager_id}: delivery failed ({type(exc).__name__}).')
                continue
            counts[result] += 1
            self.stdout.write(f'Manager {manager_id}: {result} ({requests} pending requests)')
        self.stdout.write(', '.join(f'{key}={value}' for key, value in counts.items()))
        if counts['failed']:
            raise CommandError(f'{counts["failed"]} manager digest(s) failed; rerun after fixing email delivery.')
