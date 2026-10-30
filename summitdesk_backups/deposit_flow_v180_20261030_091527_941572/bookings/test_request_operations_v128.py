"""v128 regression coverage: manager isolation, prioritization and safe export."""
import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Reservation, ReservationItem, Room


class RequestOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user(username='v128-manager', password='test')
        cls.other_manager = User.objects.create_user(username='v128-other', password='test')
        cls.unassigned = User.objects.create_user(username='v128-unassigned', password='test', is_staff=True)
        cls.admin = User.objects.create_superuser(username='v128-admin', password='test')
        cls.hut = Hut.objects.create(name='Hut North', slug='v128-north')
        cls.other_hut = Hut.objects.create(name='Hut South', slug='v128-south')
        cls.hut.managers.add(cls.manager)
        cls.other_hut.managers.add(cls.other_manager)
        cls.room = Room.objects.create(hut=cls.hut, name='Dorm', capacity=8, price_per_night=Decimal('21.00'))
        cls.other_room = Room.objects.create(hut=cls.other_hut, name='Loft', capacity=8, price_per_night=Decimal('19.00'))
        cls.today = timezone.localdate()
        cls.queue = reverse('bookings:approval_dashboard')
        cls.export = reverse('bookings:request_export')

    def make_request(self, *, name='Own Guest', room=None, days=8, status='pending', guest_request=True, old=False, notes='', code=None):
        room = room or self.room
        r = Reservation.objects.create(
            code=code if code is not None else f'RQ128{Reservation.objects.count() + 1:06d}',
            name=name, email='guest@example.com', phone='555', notes=notes,
            check_in=self.today + timedelta(days=days),
            check_out=self.today + timedelta(days=days + 2),
            status=status, guest_request=guest_request,
        )
        ReservationItem.objects.create(
            reservation=r, room=room, beds=2, price_per_night=room.price_per_night
        )
        if old:
            Reservation.objects.filter(pk=r.pk).update(created=timezone.now() - timedelta(hours=30))
            r.refresh_from_db()
        return r

    def csv_rows(self, params=None):
        response = self.client.get(self.export, params or {})
        self.assertEqual(response.status_code, 200)
        data = b''.join(response.streaming_content).decode('utf-8-sig')
        return response, list(csv.DictReader(StringIO(data)))

    def test_anonymous_and_unassigned_cannot_export(self):
        self.assertEqual(self.client.get(self.export).status_code, 302)
        self.client.force_login(self.unassigned)
        self.assertEqual(self.client.get(self.export).status_code, 403)

    def test_other_hut_not_exported_or_searchable(self):
        own = self.make_request(name='Own Guest')
        self.make_request(name='Private Other Guest', room=self.other_room)
        self.make_request(name='Internal Staff Booking', guest_request=False)
        self.client.force_login(self.manager)
        response, rows = self.csv_rows({'status': 'all'})
        self.assertEqual([r['Reference'] for r in rows], [own.code])
        self.assertNotIn('Private Other Guest', str(rows))
        self.assertNotIn('Internal Staff Booking', str(rows))
        self.assertEqual(response['Cache-Control'], 'private, no-store, max-age=0')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(self.client.get(self.export, {'hut': self.other_hut.slug}).status_code, 404)
        self.assertEqual(self.client.get(self.queue, {'hut': self.other_hut.slug}).status_code, 404)

    def test_multi_hut_reservation_is_not_exposed_to_partial_manager(self):
        r = self.make_request(name='Mixed Hut Guest')
        ReservationItem.objects.create(
            reservation=r, room=self.other_room, beds=1,
            price_per_night=self.other_room.price_per_night,
        )
        self.client.force_login(self.manager)
        _, rows = self.csv_rows()
        self.assertEqual(rows, [])
        self.assertNotContains(self.client.get(self.queue), 'Mixed Hut Guest')

    def test_superuser_hut_scope_and_all_huts(self):
        own = self.make_request(name='North Guest')
        other = self.make_request(name='South Guest', room=self.other_room)
        self.client.force_login(self.admin)
        _, rows = self.csv_rows({'status': 'all'})
        self.assertEqual({r['Reference'] for r in rows}, {own.code, other.code})
        _, rows = self.csv_rows({'status': 'all', 'hut': self.other_hut.slug})
        self.assertEqual([r['Reference'] for r in rows], [other.code])

    def test_aging_and_arrival_filters_match_dashboard_and_export(self):
        old = self.make_request(name='Old Waiting', old=True)
        due = self.make_request(name='Arriving Tomorrow', days=1)
        self.make_request(name='New Not Urgent')
        self.client.force_login(self.manager)
        response = self.client.get(self.queue)
        self.assertEqual(response.context['priority_counts'], {'waiting24': 1, 'arrival48': 1})
        self.assertContains(response, 'Waiting over 24 hours')
        self.assertContains(response, 'Arrival due')
        self.assertContains(response, 'Download CSV')
        waiting = self.client.get(self.queue, {'priority': 'waiting24'})
        self.assertEqual(waiting.context['page'].paginator.count, 1)
        self.assertContains(waiting, 'Old Waiting')
        self.assertNotContains(waiting, 'Arriving Tomorrow')
        _, rows = self.csv_rows({'priority': 'waiting24'})
        self.assertEqual([r['Reference'] for r in rows], [old.code])
        _, rows = self.csv_rows({'priority': 'arrival48'})
        self.assertEqual([r['Reference'] for r in rows], [due.code])

    def test_status_search_and_priority_are_consistent(self):
        pending = self.make_request(name='Search Me', old=True)
        confirmed = self.make_request(name='Search Me Confirmed', status='confirmed')
        self.make_request(name='Someone Else', status='cancelled')
        self.client.force_login(self.manager)
        _, rows = self.csv_rows({'status': 'all', 'q': 'Search Me'})
        self.assertEqual({r['Reference'] for r in rows}, {pending.code, confirmed.code})
        _, rows = self.csv_rows({'status': 'all', 'q': 'Search Me', 'priority': 'waiting24'})
        self.assertEqual([r['Reference'] for r in rows], [pending.code])
        _, rows = self.csv_rows({'status': 'confirmed', 'priority': 'waiting24'})
        self.assertEqual([r['Reference'] for r in rows], [confirmed.code])
        page = self.client.get(self.queue, {'status': 'confirmed', 'priority': 'waiting24'})
        self.assertEqual(page.context['priority_filter'], 'all')

    def test_export_not_limited_to_first_page(self):
        for index in range(14):
            self.make_request(name=f'Guest {index:02d}')
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.queue).context['page'].paginator.per_page, 12)
        _, rows = self.csv_rows()
        self.assertEqual(len(rows), 14)

    def test_csv_formula_injection_is_neutralized(self):
        self.hut.name = '@malicious'
        self.hut.save(update_fields=['name'])
        self.room.name = ' =SUM(1,2)'
        self.room.save(update_fields=['name'])
        self.make_request(name='=HYPERLINK("bad")', notes='\n+CMD(1)')
        self.client.force_login(self.manager)
        _, rows = self.csv_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row['Guest name'].startswith("'="))
        self.assertTrue(row['Hut'].startswith("'@"))
        self.assertTrue(row['Rooms'].startswith("' "))
        self.assertTrue(row['Guest notes'].startswith("' "))

    def test_dash_prefixed_reference_is_escaped_without_changing_the_booking(self):
        reservation = self.make_request(code='-rtP8iXk8FD5', days=1)
        self.client.force_login(self.manager)
        _, rows = self.csv_rows({'priority': 'arrival48'})
        self.assertEqual([row['Reference'] for row in rows], ["'-rtP8iXk8FD5"])
        page = self.client.get(self.queue, {'priority': 'arrival48'})
        self.assertEqual([r.code for r in page.context['page']], ['-rtP8iXk8FD5'])
        reservation.refresh_from_db()
        self.assertEqual(reservation.code, '-rtP8iXk8FD5')

    def test_export_is_read_only_get_only_and_empty_export_has_header(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.export).status_code, 405)
        response, rows = self.csv_rows()
        self.assertEqual(rows, [])
        self.assertIn('Reference', b''.join(self.client.get(self.export).streaming_content).decode('utf-8-sig'))
        self.assertEqual(Reservation.objects.count(), 0)

    def test_pagination_keeps_priority(self):
        for index in range(13):
            self.make_request(name=f'Old {index}', old=True)
        self.client.force_login(self.manager)
        response = self.client.get(self.queue, {'priority': 'waiting24'})
        self.assertContains(response, 'priority=waiting24')
        self.assertEqual(response.context['page'].paginator.count, 13)
