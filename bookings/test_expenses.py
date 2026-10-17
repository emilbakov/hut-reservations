from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Hut, HutExpense, Room, Reservation, ReservationItem, PaymentTransaction

class ExpenseManagementTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.staff = U.objects.create_user(username='exp_staff', password='pass', is_staff=True)
        self.other = U.objects.create_user(username='exp_other', password='pass', is_staff=True)
        self.hut = Hut.objects.create(name='Expenses Hut', slug='expenses-hut')
        self.other_hut = Hut.objects.create(name='Other Expenses Hut', slug='other-expenses-hut')
        self.hut.managers.add(self.staff)
        self.other_hut.managers.add(self.other)
        room = Room.objects.create(hut=self.hut, name='A', capacity=2)
        today = timezone.localdate()
        self.reservation = Reservation.objects.create(name='Guest', check_in=today, check_out=today + timedelta(days=1))
        ReservationItem.objects.create(reservation=self.reservation, room=room, beds=1, price_per_night=Decimal('100.00'))
        self.url = reverse('bookings:expense_dashboard')
        self.export = reverse('bookings:expense_export')
        self.client.force_login(self.staff)

    def add_expense(self, hut=None, amount='25.00'):
        return HutExpense.objects.create(hut=hut or self.hut, category='food', expense_date=timezone.localdate(),
                                         amount=Decimal(amount), description='Supplies', recorded_by=self.staff)

    def test_create_expense(self):
        response = self.client.post(self.url, {'hut_id': str(self.hut.pk), 'category': 'food',
            'expense_date': timezone.localdate().isoformat(), 'amount': '25.50',
            'description': 'Supplies', 'reference': 'Receipt-1'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(HutExpense.objects.count(), 1)
        self.assertEqual(HutExpense.objects.first().recorded_by, self.staff)

    def test_reject_negative_amount(self):
        response = self.client.post(self.url, {'hut_id': str(self.hut.pk), 'category': 'food',
            'expense_date': timezone.localdate().isoformat(), 'amount': '-5', 'description': 'Bad'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(HutExpense.objects.count(), 0)

    def test_cross_hut_post_denied(self):
        response = self.client.post(self.url, {'hut_id': str(self.other_hut.pk), 'category': 'food',
            'expense_date': timezone.localdate().isoformat(), 'amount': '5.00', 'description': 'Unauthorized'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(HutExpense.objects.exists())

    def test_selected_hut_cannot_be_bypassed(self):
        U = get_user_model()
        root = U.objects.create_superuser(username='exp_root', password='pass', email='root@example.com')
        self.client.force_login(root)
        response = self.client.post(self.url + '?hut=expenses-hut', {'hut_id': str(self.other_hut.pk),
            'category': 'food', 'expense_date': timezone.localdate().isoformat(),
            'amount': '5', 'description': 'Wrong hut'})
        self.assertEqual(response.status_code, 400)

    def test_cash_flow_deducts_expenses(self):
        PaymentTransaction.objects.create(reservation=self.reservation, kind='payment',
            method='cash', amount=Decimal('100.00'), recorded_by=self.staff)
        self.add_expense(amount='25.00')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['net_cash'], Decimal('100.00'))
        self.assertEqual(response.context['net_after_expenses'], Decimal('75.00'))

    def test_other_hut_expenses_not_exposed(self):
        self.add_expense(hut=self.other_hut, amount='900.00')
        response = self.client.get(self.url)
        self.assertEqual(response.context['expense_total'], Decimal('0.00'))
        self.assertNotContains(response, '900.00')
        self.assertNotIn(b'900.00', self.client.get(self.export).content)

    def test_export(self):
        self.add_expense()
        response = self.client.get(self.export)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Supplies', response.content)
        self.assertIn(b'Net cash after expenses', response.content)

    def test_invalid_month(self):
        self.assertEqual(self.client.get(self.url + '?month=13').status_code, 400)

    def test_non_staff_redirected(self):
        U = get_user_model()
        regular = U.objects.create_user(username='exp_regular', password='pass')
        self.client.force_login(regular)
        self.assertEqual(self.client.get(self.url).status_code, 302)
