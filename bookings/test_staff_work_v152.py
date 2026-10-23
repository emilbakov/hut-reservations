"""Operational counts, decision safety and mobile calendar data contracts."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone, translation

from .models import (Bed, BedClosure, GuestStay, Hut, Reservation, ReservationDecision,
                     ReservationItem, Room)
from .services import create_reservation


class StaffWork152Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user('shift-manager', is_staff=True)
        cls.other = get_user_model().objects.create_user('other-manager', is_staff=True)
        cls.hut = Hut.objects.create(name='Shift Hut', slug='shift')
        cls.private = Hut.objects.create(name='Private Hut', slug='private-shift')
        cls.hut.managers.add(cls.manager)
        cls.private.managers.add(cls.other)
        cls.room = Room.objects.create(hut=cls.hut, name='Dorm', capacity=4, price_per_night=20)
        cls.hidden_room = Room.objects.create(hut=cls.private, name='Hidden Dorm', capacity=4)

    def setUp(self):
        self.today = timezone.localdate()
        self.start = self.today + timedelta(days=2)
        self.end = self.start + timedelta(days=2)
        self.client.force_login(self.manager)

    def booking(self, *, room=None, beds=2, start=None, status='pending', name='Decision Guest'):
        return create_reservation(check_in=start or self.start, check_out=(start or self.start)+timedelta(days=2),
            beds_by_room={(room or self.room).pk: beds}, status=status, name=name,
            email='guest@example.test', guest_request=True)

    def decide(self, reservation, action='confirm', **data):
        return self.client.post(reverse('bookings:manager_reservation_action', args=[reservation.code]),
                                {'action': action, 'source': 'dashboard', 'return_hut': self.hut.slug, **data})

    def undo(self, reservation, decision=None, client=None):
        decision = decision or reservation.staff_decisions.latest('pk')
        return (client or self.client).post(reverse('bookings:undo_decision', args=[reservation.code, decision.pk]), {'source':'approvals'})

    def close(self, number=1):
        bed, _ = Bed.objects.get_or_create(room=self.room, number=number)
        return BedClosure.objects.create(bed=bed, start=self.start, end=self.end)

    def test_dashboard_counts_confirmed_arrivals_separately_from_pending_and_actual_stays(self):
        pending = self.booking(start=self.today, beds=1, name='Pending today')
        pending.guest_request=False
        pending.save(update_fields=['guest_request'])
        confirmed = self.booking(start=self.today, beds=1, status='confirmed', name='Confirmed today')
        GuestStay.objects.create(reservation=confirmed, checked_in_at=timezone.now())
        page = self.client.get(reverse('bookings:dashboard'))
        self.assertEqual(page.context['arrival_count'], 1)
        self.assertEqual(page.context['pending_count'], 1)
        self.assertEqual(page.context['in_house_count'], 1)
        self.assertEqual(page.context['occupied'], 2)
        self.assertEqual([row['reservation'].pk for row in page.context['upcoming']], [confirmed.pk])
        self.assertContains(page, 'Today')
        self.assertContains(page, 'Beds held tonight')
        self.assertNotContains(page, 'sd135-banner')
        self.assertNotContains(page, 'Quick access')
        self.assertContains(page, 'href="/staff/reservations/?status=pending&amp;hut=shift"')
        pending_list=self.client.get(reverse('bookings:manager_reservations'), {'status':'pending','hut':self.hut.slug})
        self.assertEqual([r.pk for r in pending_list.context['page']], [pending.pk])

    def test_oldest_pending_requests_are_first_and_unauthorized_huts_never_leak(self):
        first = self.booking(beds=1, name='Oldest')
        second = self.booking(beds=1, name='Newest')
        self.booking(room=self.hidden_room, name='Secret Guest')
        page = self.client.get(reverse('bookings:dashboard'))
        self.assertEqual([r.pk for r in page.context['pending_requests']], [first.pk,second.pk])
        self.assertNotContains(page, 'Secret Guest')
        self.assertContains(page, 'Needs your decision')
        self.assertContains(page, 'available before this request')
        self.assertNotContains(page, 'confirm(')

    def test_capacity_excludes_own_hold_and_uses_minimum_night(self):
        reservation = self.booking(beds=2)
        self.booking(beds=1, start=self.start+timedelta(days=1))
        self.close()
        page = self.client.get(reverse('bookings:approval_dashboard'))
        row = next(r for r in page.context['page'] if r.pk == reservation.pk)
        self.assertEqual(row.capacity_rows[0]['available'], 2)
        self.assertEqual(row.capacity_rows[0]['remaining'], 0)
        self.assertTrue(row.capacity_ok)
        self.assertEqual(self.decide(reservation).status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'confirmed')

    def test_closure_added_after_render_blocks_real_approval(self):
        reservation = self.booking(beds=4)
        self.client.get(reverse('bookings:approval_dashboard'))
        self.close()
        response = self.decide(reservation)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'pending')
        self.assertFalse(ReservationDecision.objects.exists())
        self.assertFalse(reservation.delivery_notifications.exists())
        self.assertContains(self.client.get(response.url), 'Capacity conflict')

    def test_inactive_room_cannot_be_approved(self):
        reservation = self.booking()
        self.room.is_active=False;self.room.save(update_fields=['is_active'])
        self.decide(reservation)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'pending')

    def test_decline_reason_audit_and_guest_notification_share_one_commit(self):
        reservation = self.booking()
        with self.captureOnCommitCallbacks(execute=True):
            self.decide(reservation, 'cancel', reason='Access road closed. Please call us.')
        decision = reservation.staff_decisions.get()
        self.assertEqual(decision.actor, self.manager)
        self.assertEqual(decision.before, 'pending')
        self.assertEqual(decision.after, 'cancelled')
        self.assertEqual(decision.reason, 'Access road closed. Please call us.')
        notification = reservation.delivery_notifications.get(kind='declined_guest')
        self.assertIn(decision.reason, notification.body)
        self.assertEqual(notification.status, 'sent')

    def test_oversized_reason_does_not_change_booking(self):
        reservation = self.booking()
        self.decide(reservation, 'cancel', reason='x'*1001)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status,'pending')
        self.assertFalse(reservation.staff_decisions.exists())

    def test_notification_queue_failure_rolls_back_decision_and_status(self):
        reservation = self.booking()
        with patch('bookings.notifications_v145.queue_notification', side_effect=RuntimeError('queue unavailable')):
            with self.assertRaises(RuntimeError):self.decide(reservation)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status,'pending')
        self.assertFalse(reservation.staff_decisions.exists())

    def test_undo_approval_returns_pending_and_supersedes_unsent_confirmation(self):
        reservation = self.booking()
        self.decide(reservation)
        decision = reservation.staff_decisions.get()
        page = self.client.get(reverse('bookings:dashboard'))
        self.assertContains(page,'Undo decision')
        self.undo(reservation, decision)
        reservation.refresh_from_db();decision.refresh_from_db()
        self.assertEqual(reservation.status,'pending')
        self.assertIsNotNone(decision.undone_at)
        self.assertEqual(reservation.delivery_notifications.get(kind='confirmation_guest').status,'skipped')
        self.assertEqual(reservation.delivery_notifications.get(kind='decision_undo_guest').status,'pending')
        self.undo(reservation, decision)
        self.assertEqual(reservation.delivery_notifications.filter(kind='decision_undo_guest').count(),1)

    def test_undo_decline_rechecks_released_beds(self):
        reservation = self.booking(beds=4)
        self.decide(reservation,'cancel')
        self.booking(beds=4, name='Took released beds')
        self.undo(reservation)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status,'cancelled')
        self.assertIsNone(reservation.staff_decisions.get().undone_at)

    def test_undo_decline_when_beds_still_free_restores_hold(self):
        reservation = self.booking(beds=4)
        self.decide(reservation,'cancel')
        self.undo(reservation)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status,'pending')

    def test_expired_undo_does_not_change_status(self):
        reservation = self.booking()
        self.decide(reservation)
        reservation.staff_decisions.update(created_at=timezone.now()-timedelta(minutes=6))
        self.undo(reservation)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status,'confirmed')

    def test_booking_edit_invalidates_undo_even_if_reverted(self):
        reservation = self.booking()
        self.decide(reservation)
        reservation.refresh_from_db()
        reservation.name='Changed';reservation.save(update_fields=['name'])
        reservation.name='Decision Guest';reservation.save(update_fields=['name'])
        self.undo(reservation)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status,'confirmed')

    def test_checked_in_booking_cannot_be_undone(self):
        reservation = self.booking(start=self.today)
        self.decide(reservation)
        GuestStay.objects.create(reservation=reservation,checked_in_at=timezone.now())
        self.undo(reservation)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status,'confirmed')

    def test_undo_requires_original_actor_authorized_hut_and_post(self):
        reservation = self.booking()
        self.decide(reservation)
        decision=reservation.staff_decisions.get()
        self.assertEqual(self.client.get(reverse('bookings:undo_decision',args=[reservation.code,decision.pk])).status_code,405)
        other=Client();other.force_login(self.other)
        self.assertEqual(self.undo(reservation,decision,other).status_code,404)
        self.hut.managers.add(self.other)
        self.assertEqual(self.undo(reservation,decision,other).status_code,404)

    def test_csrf_is_enforced_for_decision_and_undo(self):
        reservation = self.booking();self.decide(reservation)
        client=Client(enforce_csrf_checks=True);client.force_login(self.manager)
        self.assertEqual(client.post(reverse('bookings:manager_reservation_action',args=[reservation.code]),{'action':'cancel'}).status_code,403)
        self.assertEqual(self.undo(reservation,client=client).status_code,403)

    def test_repeat_decision_does_not_queue_duplicate_and_reapproval_after_undo_is_new_event(self):
        reservation=self.booking();self.decide(reservation);self.decide(reservation)
        self.assertEqual(reservation.staff_decisions.count(),1)
        self.undo(reservation);self.decide(reservation)
        self.assertEqual(reservation.staff_decisions.count(),2)
        self.assertEqual(reservation.delivery_notifications.filter(kind='confirmation_guest').count(),2)
        self.assertEqual(reservation.delivery_notifications.get(kind='decision_undo_guest').status,'skipped')

    def test_week_counts_closures_checkout_and_inactive_rooms(self):
        self.booking(beds=2);self.close()
        # A duplicate closure for the same physical bed must count only once.
        self.close()
        page=self.client.get(reverse('bookings:calendar_timeline'),{'start':self.start.isoformat()})
        self.assertEqual(len(page.context['agenda']),7)
        self.assertEqual([day['free'] for day in page.context['agenda']][:3],[1,1,4])
        self.assertContains(page,'sd152-agenda')
        self.assertContains(page,'Today</a>')
        self.assertContains(page,'data-sd152-auto')
        self.room.is_active=False;self.room.save(update_fields=['is_active'])
        page=self.client.get(reverse('bookings:calendar_timeline'),{'start':self.start.isoformat()})
        self.assertEqual(page.context['agenda'][0]['free'],0)

    def test_mixed_hut_bookings_consume_capacity_without_exposing_guest(self):
        reservation=self.booking(name='Mixed secret')
        ReservationItem.objects.create(reservation=reservation,room=self.hidden_room,beds=1,price_per_night=20)
        for route in ['dashboard','calendar_timeline']:
            page=self.client.get(reverse('bookings:'+route),{'start':self.start.isoformat()})
            self.assertNotContains(page,'Mixed secret')
        self.assertEqual(page.context['agenda'][0]['free'],2)

    def test_navigation_includes_money_tools_and_does_not_duplicate_guest_tools(self):
        page=self.client.get(reverse('bookings:dashboard'))
        self.assertContains(page,reverse('bookings:expense_dashboard'))
        self.assertContains(page,reverse('bookings:deposit_dashboard'))
        self.assertNotContains(page,'Guest communication')
        self.assertNotContains(page,'Guest approvals')
        self.assertContains(page,'class="sd116-skip"')
        self.assertContains(page,'tabindex="-1"')
        self.assertNotContains(page,'fonts.googleapis.com')
        self.assertNotContains(page,'fonts.gstatic.com')
        self.assertContains(page,'local_fonts_v152.css')

    def test_monthly_counts_match_weekly_closures_and_hide_mixed_hut_guest(self):
        reservation=self.booking(name='Private mixed monthly')
        ReservationItem.objects.create(reservation=reservation,room=self.hidden_room,beds=1,price_per_night=20)
        self.close();self.close()
        page=self.client.get(reverse('bookings:availability_calendar'),{'year':self.start.year,'month':self.start.month})
        cell=next(c for c in page.context['rows'][0]['days'] if c['day']==self.start)
        self.assertEqual(cell['available'],1)
        self.assertEqual(cell['blocked'],1)
        self.assertEqual(cell['booked'],2)
        self.assertEqual(cell['reservations'],[])
        self.assertNotContains(page,'Private mixed monthly')
        self.room.is_active=False;self.room.save(update_fields=['is_active'])
        page=self.client.get(reverse('bookings:availability_calendar'),{'year':self.start.year,'month':self.start.month})
        self.assertTrue(all(c['available']==0 for c in page.context['rows'][0]['days']))

    def test_decline_reason_is_shown_as_escaped_text_on_review_page(self):
        reservation=self.booking()
        self.decide(reservation,'cancel',reason='<script>attack()</script>')
        page=self.client.get(reverse('bookings:approval_dashboard'),{'status':'cancelled'})
        self.assertContains(page,'&lt;script&gt;attack()&lt;/script&gt;')
        self.assertNotContains(page,'<script>attack()</script>')

    def test_undo_supersedes_delivered_decision_with_one_correction_email(self):
        from django.core import mail
        reservation=self.booking()
        with self.captureOnCommitCallbacks(execute=True):self.decide(reservation,'cancel')
        self.assertEqual(len(mail.outbox),1)
        with self.captureOnCommitCallbacks(execute=True):self.undo(reservation)
        self.assertEqual(len(mail.outbox),2)
        self.assertIn('awaiting approval again',mail.outbox[-1].body)
        self.assertIn(self.hut.name,mail.outbox[-1].body)
        self.assertEqual(reservation.delivery_notifications.get(kind='decision_undo_guest').status,'sent')

    def test_bulgarian_new_dashboard_labels(self):
        with translation.override('bg'):
            page=self.client.get(reverse('bookings:dashboard'),HTTP_ACCEPT_LANGUAGE='bg')
        self.assertContains(page,'Нуждаят се от решение')
