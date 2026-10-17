from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .deposits import deposit_summary
from .models import Hut, HutDepositPolicy, DepositReminderLog, Room, Reservation, ReservationItem, PaymentTransaction


class DepositTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user(username='dep_manager', password='pass', is_staff=True)
        self.other = U.objects.create_user(username='dep_other', password='pass', is_staff=True)
        self.hut = Hut.objects.create(name='Deposit Hut', slug='deposit-hut')
        self.foreign = Hut.objects.create(name='Foreign Deposit Hut', slug='foreign-deposit-hut')
        self.hut.managers.add(self.staff)
        self.foreign.managers.add(self.other)
        room = Room.objects.create(hut=self.hut, name='A', capacity=2)
        self.res = Reservation.objects.create(name='Guest', email='guest@example.com',
            check_in=timezone.localdate() + timedelta(days=7), check_out=timezone.localdate() + timedelta(days=8))
        ReservationItem.objects.create(reservation=self.res, room=room, beds=1, price_per_night=Decimal('100.00'))
        self.client.force_login(self.staff)
        self.url = reverse('bookings:deposit_dashboard')

    def test_default_policy(self):
        result = deposit_summary(self.res)
        self.assertEqual(result['target'], Decimal('30.00'))
        self.assertEqual(result['remaining'], Decimal('30.00'))

    def test_payments_and_refunds(self):
        PaymentTransaction.objects.create(reservation=self.res, kind='deposit', method='cash', amount=Decimal('20'), recorded_by=self.staff)
        PaymentTransaction.objects.create(reservation=self.res, kind='refund', method='cash', amount=Decimal('5'), recorded_by=self.staff)
        self.assertEqual(deposit_summary(self.res)['remaining'], Decimal('15.00'))

    def test_policy_update(self):
        response = self.client.post(self.url, {'hut_id': self.hut.pk, 'percentage': 50, 'due_days': 5, 'reminders_enabled': 'on'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(deposit_summary(self.res)['target'], Decimal('50.00'))
        self.assertTrue(HutDepositPolicy.objects.get(hut=self.hut).reminders_enabled)

    def test_invalid_policy_rejected(self):
        self.client.post(self.url, {'hut_id': self.hut.pk, 'percentage': 101, 'due_days': 5})
        self.assertFalse(HutDepositPolicy.objects.exists())

    def test_foreign_hut_rejected(self):
        response = self.client.post(self.url, {'hut_id': self.foreign.pk, 'percentage': 50, 'due_days': 5})
        self.assertEqual(response.status_code, 404)

    def test_cancelled_not_overdue(self):
        self.res.status = Reservation.Status.CANCELLED
        self.res.save(update_fields=['status'])
        self.assertFalse(deposit_summary(self.res, today=timezone.localdate() + timedelta(days=10))['overdue'])

    def test_overdue_dashboard(self):
        self.res.created = timezone.now() - timedelta(days=8)
        self.res.save(update_fields=['created'])
        response = self.client.get(self.url)
        self.assertEqual(response.context['overdue_count'], 1)

    @patch('bookings.management.commands.send_deposit_reminders.send_mail')
    def test_reminder_sent_once(self, mocked):
        self.res.created = timezone.now() - timedelta(days=8)
        self.res.save(update_fields=['created'])
        call_command('send_deposit_reminders')
        call_command('send_deposit_reminders')
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(DepositReminderLog.objects.count(), 1)

    @patch('bookings.management.commands.send_deposit_reminders.send_mail')
    def test_no_reminder_if_disabled(self, mocked):
        self.res.created = timezone.now() - timedelta(days=8)
        self.res.save(update_fields=['created'])
        HutDepositPolicy.objects.create(hut=self.hut, reminders_enabled=False)
        call_command('send_deposit_reminders')
        mocked.assert_not_called()

    @patch('bookings.management.commands.send_deposit_reminders.send_mail')
    def test_dry_run_does_not_send(self, mocked):
        self.res.created = timezone.now() - timedelta(days=8)
        self.res.save(update_fields=['created'])
        call_command('send_deposit_reminders', dry_run=True)
        mocked.assert_not_called()
        self.assertFalse(DepositReminderLog.objects.exists())
