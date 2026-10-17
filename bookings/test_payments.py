from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Hut, Room, Reservation, ReservationItem, PaymentTransaction
from .payments import balance

class PaymentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='payment_manager', password='testpass', is_staff=True)
        self.outsider = get_user_model().objects.create_user(username='payment_outsider', password='testpass', is_staff=True)
        self.hut = Hut.objects.create(name='Payment Hut', slug='payment-hut')
        self.hut.managers.add(self.user)
        self.room = Room.objects.create(hut=self.hut, name='Room A', capacity=3, price_per_night=Decimal('40.00'))
        today = timezone.localdate()
        self.reservation = Reservation.objects.create(name='Guest', check_in=today + timedelta(days=1), check_out=today + timedelta(days=2))
        ReservationItem.objects.create(reservation=self.reservation, room=self.room, beds=2, price_per_night=Decimal('40.00'))
        self.url = reverse('bookings:reservation_payments', args=[self.reservation.code])
        self.client.force_login(self.user)

    def record(self, kind, amount, method='cash'):
        return self.client.post(self.url, {'kind': kind, 'amount': amount, 'method': method, 'note': 'Manual receipt'})

    def test_initial_balance(self):
        self.assertEqual(balance(self.reservation)['due'], Decimal('80.00'))

    def test_deposit_and_payment(self):
        self.assertEqual(self.record('deposit', '30.00').status_code, 302)
        self.assertEqual(self.record('payment', '50.00').status_code, 302)
        self.assertEqual(balance(self.reservation)['status'], 'paid')

    def test_refund_changes_balance(self):
        self.record('deposit', '30.00')
        self.record('refund', '10.00')
        self.assertEqual(balance(self.reservation)['due'], Decimal('60.00'))

    def test_refund_cannot_exceed_received(self):
        self.record('refund', '1.00')
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    def test_invalid_amount_rejected(self):
        self.record('payment', 'NaN')
        self.record('payment', '-2.00')
        self.record('payment', '2.999')
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    def test_other_hut_manager_cannot_access(self):
        self.client.force_login(self.outsider)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)
        self.assertNotEqual(self.record('payment', '10.00').status_code, 302)
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    def test_cancelled_reservation_can_refund(self):
        self.record('payment', '80.00')
        self.reservation.status = Reservation.Status.CANCELLED
        self.reservation.save(update_fields=['status'])
        self.record('refund', '80.00')
        self.assertEqual(balance(self.reservation)['net'], Decimal('0.00'))
