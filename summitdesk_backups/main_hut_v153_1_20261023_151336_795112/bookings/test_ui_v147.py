"""Query budgets, locale-safe booking, and language-switch isolation."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .availability_v147 import nightly_availability
from .models import Bed, BedClosure, Hut, Reservation, ReservationItem, Room
from .services import free_beds
from .views import availability_calendar


class RangeAvailability147Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.first = (cls.today.replace(day=28) + timedelta(days=4)).replace(day=1)
        cls.hut = Hut.objects.create(name='Range Lodge', slug='range-lodge')
        cls.room = Room.objects.create(hut=cls.hut, name='Dorm', capacity=5)
        cls.twin = Room.objects.create(hut=cls.hut, name='Twin', capacity=2)
        cls.inactive = Room.objects.create(hut=cls.hut, name='Inactive', capacity=40, is_active=False)
        cls.hidden = Hut.objects.create(name='Hidden Lodge', slug='hidden-lodge', is_active=False)
        cls.secret = Room.objects.create(hut=cls.hidden, name='Hidden capacity', capacity=50)

    def booking(self, room, beds, start=0, end=4, status='confirmed'):
        stay = Reservation.objects.create(name='Never in public JSON', email='private@example.com',
            check_in=self.first + timedelta(days=start), check_out=self.first + timedelta(days=end), status=status)
        ReservationItem.objects.create(reservation=stay, room=room, beds=beds)
        return stay

    def test_range_matches_authoritative_service_every_night(self):
        self.booking(self.room, 3, start=-2, end=3)
        self.booking(self.room, 2, start=1, end=5, status='pending')
        self.booking(self.twin, 2, start=0, end=4, status='cancelled')
        self.booking(self.secret, 50)
        bed = Bed.objects.create(room=self.room, number=1)
        for start, end in ((0, 3), (1, 4)):
            BedClosure.objects.create(bed=bed, start=self.first+timedelta(days=start),
                                     end=self.first+timedelta(days=end), reason='Inspection')
        rooms = [self.room, self.twin]
        with self.assertNumQueries(2):
            result = nightly_availability(rooms, self.first, self.first+timedelta(days=31))
        for night, actual in result.items():
            self.assertEqual(actual, free_beds(rooms, night, night+timedelta(days=1)))
        self.assertEqual(result[self.first][self.room.pk], 1)
        self.assertEqual(result[self.first+timedelta(days=1)][self.room.pk], 0)
        self.assertEqual(result[self.first+timedelta(days=5)][self.room.pk], 5)

    def test_month_query_budget_is_four_for_a_hut_and_three_globally(self):
        self.booking(self.room, 2)
        factory = RequestFactory()
        params = {'year':self.first.year, 'month':self.first.month}
        for extra, budget in (({'hut':self.hut.slug},4), ({},3)):
            with self.subTest(extra=extra), self.assertNumQueries(budget):
                response = availability_calendar(factory.get('/availability/calendar/', {**params, **extra}))
            self.assertEqual(response.status_code, 200)
            import json
            data = json.loads(response.content)
            self.assertEqual(data['capacity'], 7)
            self.assertNotIn(str(self.secret.pk), data['days'][0]['rooms'])
            self.assertNotIn(str(self.inactive.pk), data['days'][0]['rooms'])
            self.assertNotIn('private@example.com', response.content.decode())

    def test_query_count_is_constant_as_rooms_and_days_grow(self):
        rooms = [self.room, self.twin]
        for i in range(10):
            rooms.append(Room.objects.create(hut=self.hut, name=f'Room {i}', capacity=3))
        with self.assertNumQueries(2):
            result = nightly_availability(rooms, self.first, self.first+timedelta(days=90))
        self.assertEqual(len(result), 90)
        self.assertEqual(len(result[self.first]), 12)

    def test_empty_ranges_need_no_inventory_queries(self):
        with self.assertNumQueries(0):
            self.assertEqual(nightly_availability([], self.first, self.first+timedelta(days=1)), {})
            self.assertEqual(nightly_availability([self.room], self.first, self.first), {})

    def test_no_cache_serves_stale_availability(self):
        before = nightly_availability([self.room], self.first, self.first+timedelta(days=1))
        self.booking(self.room, 4)
        after = nightly_availability([self.room], self.first, self.first+timedelta(days=1))
        self.assertEqual(before[self.first][self.room.pk]-after[self.first][self.room.pk], 4)

    def test_invalid_or_out_of_window_month_does_not_query_inventory(self):
        for year, month in (('bad',1),(9999,12),(2026,13),(2000,1)):
            with self.subTest(year=year, month=month), self.assertNumQueries(0):
                response = availability_calendar(RequestFactory().get('/',{'year':year,'month':month}))
            self.assertEqual(response.status_code,400)

    @override_settings(BOOKING_MAX_DAYS_AHEAD=9)
    def test_current_month_is_clipped_to_booking_window(self):
        result = self.client.get(reverse('bookings:calendar'), {'year':self.today.year,'month':self.today.month}).json()
        self.assertTrue(result['days'])
        for day in result['days']:
            self.assertGreaterEqual(day['date'], self.today.isoformat())
            self.assertLessEqual(day['date'], (self.today+timedelta(days=9)).isoformat())


class Locale147Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hut = Hut.objects.create(name='Българска хижа', slug='locale-lodge')
        cls.room = Room.objects.create(hut=cls.hut, name='Стая <script>alert(1)</script>',
            capacity=4, price_per_night=Decimal('24.50'))
        cls.start = timezone.localdate()+timedelta(days=3)
        cls.end = cls.start+timedelta(days=2)
        cls.manager = get_user_model().objects.create_user('locale-manager', is_staff=True)
        cls.hut.managers.add(cls.manager)

    def dates(self):
        return {'check_in':self.start.isoformat(),'check_out':self.end.isoformat(),'beds':'2'}

    def url(self):
        return reverse('bookings:hut_detail',args=[self.hut.slug])

    def bulgarian(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'bg'

    def test_language_switch_preserves_query_and_sets_only_language(self):
        target = self.url()+'?check_in='+self.start.isoformat()+'&check_out='+self.end.isoformat()+'&beds=2'
        response = self.client.post(reverse('set_language'),{'language':'bg','next':target})
        self.assertRedirects(response,target,fetch_redirect_response=False)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value,'bg')
        page = self.client.get(target)
        self.assertContains(page,'lang="bg"')
        self.assertContains(page,'Изпрати заявка')
        self.assertIn('Accept-Language',page.headers.get('Vary',''))
        self.assertFalse(Reservation.objects.exists())

    def test_bg_render_and_iso_values_do_not_depend_on_browser_number_locale(self):
        self.bulgarian()
        page = self.client.get(self.url(),self.dates())
        self.assertEqual(page.headers['Content-Language'],'bg')
        self.assertContains(page,'Обобщение на заявката')
        self.assertContains(page,'24,50')
        self.assertContains(page,'data-price="24.50"')
        self.assertContains(page,'value="'+self.start.isoformat()+'"')
        self.assertContains(page,'Стая &lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(page,'Стая <script>')

    def test_locale_specific_errors_keep_details_and_do_not_write(self):
        self.bulgarian()
        data={**self.dates(),'beds':'3','name':'Запазено име','email':'kept@example.com',f'room_{self.room.pk}':'2'}
        page=self.client.post(self.url(),data)
        self.assertContains(page,'Избери точно 3 легла')
        self.assertContains(page,'Запазено име')
        self.assertEqual(page.context['estimated_total'],Decimal('98.00'))
        self.assertFalse(Reservation.objects.exists())

    def test_bg_submission_remains_pending_and_idempotent(self):
        self.bulgarian()
        page=self.client.get(self.url(),self.dates())
        data={**self.dates(),'name':'Гост','email':'guest@example.com',f'room_{self.room.pk}':'2',
              'submission_token':page.context['submission_token']}
        first=self.client.post(self.url(),data)
        again=self.client.post(self.url(),data)
        self.assertEqual(first.status_code,302)
        self.assertEqual(first.url,again.url)
        self.assertEqual(Reservation.objects.count(),1)
        booking=Reservation.objects.get()
        self.assertEqual(booking.status,Reservation.Status.PENDING)
        self.assertEqual(booking.items.get().price_per_night,Decimal('24.50'))
        receipt=self.client.get(first.url)
        self.assertContains(receipt,'Очаква одобрение')
        self.assertContains(receipt,'98,00')

    def test_staff_planner_is_localized_but_pricing_attributes_remain_numeric(self):
        self.bulgarian();self.client.force_login(self.manager)
        page=self.client.get(reverse('floorplans:staff_calendar',args=[self.hut.pk]))
        self.assertContains(page,'Месечен планер на престои')
        self.assertContains(page,'Потвърди резервацията')
        self.assertContains(page,'Page Up')
        self.assertContains(page,'data-price="24.50"')
        self.assertContains(page,'24,50')

    def test_older_staff_booking_forms_have_locale_safe_prices(self):
        self.bulgarian();self.client.force_login(self.manager)
        for url,extra in ((reverse('bookings:manual_booking'),{'hut':self.hut.pk}),
                          (reverse('floorplans:staff_new_booking',args=[self.hut.pk]),{})):
            page=self.client.get(url,{**self.dates(),**extra})
            self.assertContains(page,'data-price="24.50"')

    def test_language_switch_rejects_external_redirect_and_needs_csrf(self):
        response=self.client.post(reverse('set_language'),{'language':'bg','next':'https://example.net/steal'})
        self.assertEqual(response.url,'/')
        strict=Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse('set_language'),{'language':'bg'}).status_code,403)
        strict.get('/')
        csrf=strict.cookies['csrftoken'].value
        self.assertEqual(strict.post(reverse('set_language'),{'language':'bg','csrfmiddlewaretoken':csrf,'next':'/huts/'}).status_code,302)

    def test_english_can_be_selected_even_with_bulgarian_browser_preference(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME]='en'
        page=self.client.get(self.url(),self.dates(),HTTP_ACCEPT_LANGUAGE='bg')
        self.assertContains(page,'lang="en"')
        self.assertContains(page,'Your request summary')
        self.assertContains(page,'24.50')
