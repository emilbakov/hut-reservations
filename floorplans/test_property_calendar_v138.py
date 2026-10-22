from django.test import override_settings
"""SummitDesk v138 — property-scoped monthly calendar and legacy timeline checks."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Bed, BedClosure, Hut, Reservation, ReservationItem, Room
from .property_calendar_v138 import month_rows


@override_settings(SECURE_SSL_REDIRECT=False)
class PropertyCalendarV138Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user('v138_property_manager', password='pw', is_staff=True)
        cls.other = User.objects.create_user('v138_property_other', password='pw', is_staff=True)
        cls.hut = Hut.objects.create(name='Property Alpine Hut', slug='property-alpine-v138')
        cls.private_hut = Hut.objects.create(name='Secret Other Hut', slug='secret-other-v138')
        cls.hut.managers.add(cls.manager)
        cls.private_hut.managers.add(cls.other)
        cls.room = Room.objects.create(hut=cls.hut, name='Alpine Bunks', capacity=4)
        cls.room2 = Room.objects.create(hut=cls.hut, name='Ridge Room', capacity=3)
        cls.inactive = Room.objects.create(hut=cls.hut, name='Inactive Loft', capacity=2, is_active=False)
        cls.private_room = Room.objects.create(hut=cls.private_hut, name='Secret Room', capacity=2)
        cls.first = timezone.localdate().replace(day=1)

    def url(self, hut=None):
        return reverse('floorplans:staff_calendar', args=[(hut or self.hut).pk])

    def reserve(self, room, start, end, beds, name='Guest', status=Reservation.Status.CONFIRMED):
        reservation = Reservation.objects.create(
            name=name, email='test@example.com', check_in=start, check_out=end, status=status,
        )
        ReservationItem.objects.create(reservation=reservation, room=room, beds=beds)
        return reservation

    def test_monthly_default_all_rooms_one_hut_only(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'floorplans/property_calendar_v138.html')
        self.assertContains(response, 'Alpine Bunks')
        self.assertContains(response, 'Ridge Room')
        self.assertContains(response, 'Inactive Loft')
        self.assertNotContains(response, 'Secret Room')
        self.assertNotContains(response, 'Secret Other Hut')
        self.assertEqual(len(response.context['rows']), 3)
        self.assertContains(response, 'Detailed timeline')
        self.assertContains(response, 'view=timeline')
        self.assertContains(response, reverse('bookings:calendar_create'))

    def test_manager_cannot_open_other_hut_even_with_query_override(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.url(self.private_hut)).status_code, 404)
        response = self.client.get(self.url(), {'hut': self.private_hut.slug, 'room': self.private_room.pk})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Secret Room')

    def test_monthly_occupancy_and_checkout_exclusive(self):
        self.reserve(self.room, self.first, self.first + timedelta(days=2), 2, name='Alpine Guest')
        rows = month_rows(self.first, [self.room])
        self.assertEqual([c['booked'] for c in rows[0]['days'][:3]], [2, 2, 0])
        self.assertEqual([c['available'] for c in rows[0]['days'][:3]], [2, 2, 4])
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'year': self.first.year, 'month': self.first.month})
        self.assertContains(response, 'Alpine Guest')
        self.assertContains(response, reverse('floorplans:staff_reservation', args=[self.hut.pk, rows[0]['days'][0]['reservations'][0]['code']]))

    def test_maintenance_distinct_beds_and_cancelled_excluded(self):
        bed = Bed.objects.create(room=self.room, number=1)
        BedClosure.objects.create(bed=bed, start=self.first, end=self.first + timedelta(days=2))
        BedClosure.objects.create(bed=bed, start=self.first, end=self.first + timedelta(days=1))
        self.reserve(self.room, self.first, self.first + timedelta(days=1), 2)
        self.reserve(self.room, self.first, self.first + timedelta(days=1), 1, status=Reservation.Status.CANCELLED)
        cells = month_rows(self.first, [self.room])[0]['days']
        self.assertEqual((cells[0]['booked'], cells[0]['blocked'], cells[0]['available']), (2, 1, 1))
        self.assertEqual((cells[1]['booked'], cells[1]['blocked'], cells[1]['available']), (0, 1, 3))

    def test_cross_hut_booking_counts_but_does_not_leak_guest(self):
        mixed = self.reserve(self.room, self.first, self.first + timedelta(days=1), 1, name='Private Mixed Guest')
        ReservationItem.objects.create(reservation=mixed, room=self.private_room, beds=1)
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'year': self.first.year, 'month': self.first.month})
        self.assertEqual(response.context['rows'][0]['days'][0]['booked'], 1)
        self.assertNotContains(response, 'Private Mixed Guest')
        self.assertNotContains(response, mixed.code)

    def test_original_timeline_remains_available(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'view': 'timeline'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'floorplans/staff_calendar.html')
        self.assertContains(response, 'Room booking timeline')
        self.assertContains(response, 'Monthly overview')
        self.assertContains(response, 'name="view" value="timeline"')

    def test_anonymous_and_non_manager_cannot_access(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_invalid_month_falls_back_and_get_is_read_only(self):
        booking = self.reserve(self.room, self.first, self.first + timedelta(days=1), 1)
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'year': '999999999999999', 'month': '13'})
        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Reservation.Status.CONFIRMED)

    def test_book_buttons_only_for_future_dates_with_free_beds(self):
        from calendar import monthrange
        from datetime import date
        from urllib.parse import urlencode

        self.client.force_login(self.manager)
        today = timezone.localdate()
        # Choose a future month to avoid time-of-day and past-date assumptions.
        year = today.year + (today.month == 12)
        month = today.month % 12 + 1
        first = date(year, month, 1)
        self.reserve(self.room, first, first + timedelta(days=1), self.room.capacity)
        self.reserve(self.room2, first + timedelta(days=1), first + timedelta(days=2), 1)
        response = self.client.get(self.url(), {'year': year, 'month': month})
        self.assertEqual(response.status_code, 200)
        base = reverse('bookings:calendar_create')
        def booking_url(room, day):
            return base + '?' + urlencode({'check_in': day.isoformat(), 'room': room.pk, 'hut': self.hut.slug})
        # Full and inactive room cells must never offer a booking action.
        self.assertNotContains(response, booking_url(self.room, first))
        self.assertNotContains(response, booking_url(self.inactive, first))
        # Free cells (including partially occupied) retain hut/room/date preselection.
        self.assertContains(response, booking_url(self.room, first + timedelta(days=1)).replace('&', '&amp;'))
        self.assertContains(response, booking_url(self.room2, first + timedelta(days=1)).replace('&', '&amp;'))
        self.assertContains(response, '+ Book')

    def test_past_cells_never_have_booking_link(self):
        from datetime import date
        from urllib.parse import urlencode
        today = timezone.localdate()
        if today.day == 1:
            past = today.replace(day=1) - timedelta(days=1)
        else:
            past = today.replace(day=1)
        self.client.force_login(self.manager)
        response = self.client.get(self.url(), {'year': past.year, 'month': past.month})
        link = reverse('bookings:calendar_create') + '?' + urlencode({
            'check_in': past.isoformat(), 'room': self.room.pk, 'hut': self.hut.slug})
        self.assertNotContains(response, link)
