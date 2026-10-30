from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Hut, Room, Bed, BedClosure, BedAssignment, Reservation
from .services import create_reservation
from . import admin_room_delete_v185 as deletion
from floorplans.models import RoomPlacement, BedMarker, BedHousekeeping


@override_settings(BOOKING_UNIT="room", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdminRoomDelete185Tests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser("delete-owner", "test@example.test", "test-only")
        self.client.force_login(self.owner)
        self.hut = Hut.objects.create(name="Хижа Смолянски езера", slug="delete-test")
        self.room = Room.objects.create(hut=self.hut, name="1", capacity=10, price_per_night=30)
        self.beds = [Bed.objects.create(room=self.room, number=n) for n in range(1, 11)]
        self.other = Room.objects.create(hut=self.hut, name="2", capacity=2, price_per_night=40)
        self.url = reverse("admin:bookings_room_changelist")

    def post(self, confirm=False, rooms=None, client=None):
        data = {"action": "delete_unused_rooms", "_selected_action": [r.pk for r in (rooms or [self.room])]}
        if confirm:
            data["confirm_unused_room_delete"] = "yes"
        return (client or self.client).post(self.url, data)

    def assert_kept(self):
        self.assertTrue(Room.objects.filter(pk=self.room.pk).exists())
        self.assertEqual(Bed.objects.filter(room=self.room).count(), 10)

    def booking(self):
        start = timezone.localdate() + timedelta(days=10)
        return create_reservation(check_in=start, check_out=start + timedelta(days=2),
                                  beds_by_room={self.room.pk: 1}, name="Synthetic guest")

    def test_action_is_listed_and_preview_never_deletes(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Delete unused rooms and their beds")
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "10 attached bed record(s)")
        self.assertContains(response, "Хижа Смолянски езера")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assert_kept()

    def test_confirm_removes_only_room_beds_and_layout_and_logs_room(self):
        RoomPlacement.objects.create(room=self.room)
        BedMarker.objects.create(bed=self.beds[0], x=1, y=1)
        response = self.post(True)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Room.objects.filter(pk=self.room.pk).exists())
        self.assertFalse(Bed.objects.filter(pk__in=[b.pk for b in self.beds]).exists())
        self.assertFalse(RoomPlacement.objects.exists())
        self.assertFalse(BedMarker.objects.exists())
        self.assertTrue(Room.objects.filter(pk=self.other.pk).exists())
        self.assertTrue(Hut.objects.filter(pk=self.hut.pk).exists())
        self.assertTrue(LogEntry.objects.filter(action_flag=DELETION, object_id=str(self.room.pk)).exists())

    def test_room_without_beds_can_be_deleted(self):
        self.assertEqual(self.post(True, [self.other]).status_code, 302)
        self.assertFalse(Room.objects.filter(pk=self.other.pk).exists())
        self.assert_kept()

    def test_active_booking_is_preserved(self):
        booking = self.booking()
        response = self.post(True)
        self.assertRedirects(response, self.url)
        self.assert_kept()
        self.assertTrue(Reservation.objects.filter(pk=booking.pk).exists())

    def test_cancelled_booking_history_is_preserved(self):
        booking = self.booking()
        booking.status = Reservation.Status.CANCELLED
        booking.save(update_fields=["status"])
        self.post(True)
        self.assert_kept()

    def test_bed_assignment_blocks_deletion(self):
        booking = self.booking()
        assignment = BedAssignment.objects.create(bed=self.beds[0], item=booking.items.first())
        self.post(True)
        self.assert_kept()
        self.assertTrue(BedAssignment.objects.filter(pk=assignment.pk).exists())

    def test_bed_closure_blocks_deletion(self):
        day = timezone.localdate()
        closure = BedClosure.objects.create(bed=self.beds[0], start=day, end=day + timedelta(days=1))
        self.post(True)
        self.assert_kept()
        self.assertTrue(BedClosure.objects.filter(pk=closure.pk).exists())

    def test_cascading_housekeeping_is_preserved(self):
        history = BedHousekeeping.objects.create(bed=self.beds[0])
        self.post(True)
        self.assert_kept()
        self.assertTrue(BedHousekeeping.objects.filter(pk=history.pk).exists())

    def test_one_blocked_room_preserves_entire_selection(self):
        self.booking()
        self.post(True, [self.other, self.room])
        self.assert_kept()
        self.assertTrue(Room.objects.filter(pk=self.other.pk).exists())
        self.assertFalse(LogEntry.objects.filter(action_flag=DELETION).exists())

    def test_rechecks_when_booking_arrives_after_preview(self):
        self.post()
        self.booking()
        self.post(True)
        self.assert_kept()

    def test_rechecks_inside_transaction_after_locking(self):
        original = deletion.check_unused
        calls = []
        def check(rooms, using):
            calls.append(1)
            if len(calls) == 2:
                raise deletion.UnusedRoomError("Synthetic late dependency")
            return original(rooms, using)
        with patch.object(deletion, "check_unused", side_effect=check):
            self.post(True)
        self.assertEqual(len(calls), 2)
        self.assert_kept()

    def test_late_protection_rolls_back_beds_and_admin_log(self):
        with patch.object(Room, "delete", side_effect=ProtectedError("Synthetic late protection", [])):
            self.post(True)
        self.assert_kept()
        self.assertFalse(LogEntry.objects.filter(action_flag=DELETION).exists())

    def test_staff_without_delete_permission_cannot_run_action(self):
        user = get_user_model().objects.create_user("view-only", is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename="view_room", content_type__app_label="bookings"))
        self.client.force_login(user)
        self.post(True)
        self.assert_kept()

    def test_hut_manager_cannot_bypass_admin_protection(self):
        user = get_user_model().objects.create_user("hut-manager", is_staff=True)
        self.hut.managers.add(user)
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label="bookings", codename__in=["view_room", "delete_room"]))
        self.client.force_login(user)
        response = self.post(True)
        self.assertEqual(response.status_code, 403)
        self.assert_kept()

    def test_anonymous_and_missing_csrf_cannot_delete(self):
        self.client.logout()
        self.assertEqual(self.post(True).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(self.post(True, client=client).status_code, 403)
        self.assert_kept()

    def test_default_delete_remains_protected(self):
        response = self.client.post(reverse("admin:bookings_room_delete", args=[self.room.pk]), {"post": "yes"})
        self.assertEqual(response.status_code, 200)
        self.assert_kept()
