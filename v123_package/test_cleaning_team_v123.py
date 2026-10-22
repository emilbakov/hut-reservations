"""Regression tests for hut-scoped, name-only cleaner assignments."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from bookings.models import Bed, Hut, Room
from floorplans.housekeeping_tasks import HousekeepingTask
from floorplans.hut_staff import HutCleaner, OfflineCleaner


class CleaningTeamTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user(username='manager123', password='testpass123')
        cls.cleaner = User.objects.create_user(username='cleaner123', password='testpass123')
        cls.outsider = User.objects.create_user(username='outsider123', password='testpass123')
        cls.hut = Hut.objects.create(name='Test Mountain Hut', slug='test-mountain-hut')
        cls.other_hut = Hut.objects.create(name='Other Hut', slug='other-test-hut')
        cls.hut.managers.add(cls.manager)
        cls.room = Room.objects.create(hut=cls.hut, name='Dorm', capacity=2)
        cls.bed = Bed.objects.create(room=cls.room, number=1)

    def setUp(self):
        self.client.force_login(self.manager)
        self.team_url = reverse('floorplans:cleaner_team', args=[self.hut.pk])
        self.tasks_url = reverse('floorplans:staff_tasks', args=[self.hut.pk])

    def _assign(self, selection):
        return self.client.post(self.tasks_url, {
            'action': 'save', 'bed_id': str(self.bed.pk),
            'assignee': selection, 'priority': 'normal',
            'status': 'open', 'note': 'Clean the bed',
        })

    def test_manager_adds_name_without_user(self):
        response = self.client.post(self.team_url, {'action': 'add_offline', 'name': '  Maria   Ivanova  '})
        self.assertEqual(response.status_code, 302)
        person = OfflineCleaner.objects.get(hut=self.hut)
        self.assertEqual(person.name, 'Maria Ivanova')
        self.assertContains(self.client.get(self.team_url), 'Maria Ivanova')

    def test_name_required_and_case_insensitive_duplicate(self):
        self.client.post(self.team_url, {'action': 'add_offline', 'name': ' '})
        self.assertEqual(OfflineCleaner.objects.count(), 0)
        self.client.post(self.team_url, {'action': 'add_offline', 'name': 'Maria'})
        self.client.post(self.team_url, {'action': 'add_offline', 'name': 'mARIA'})
        self.assertEqual(OfflineCleaner.objects.count(), 1)

    def test_manager_can_add_existing_user(self):
        response = self.client.post(self.team_url, {'action': 'add', 'user_id': str(self.cleaner.pk)})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(HutCleaner.objects.filter(hut=self.hut, user=self.cleaner).exists())
        self.assertContains(self.client.get(self.team_url), 'cleaner123')

    def test_no_candidate_is_not_broken(self):
        HutCleaner.objects.create(hut=self.hut, user=self.cleaner)
        HutCleaner.objects.create(hut=self.hut, user=self.outsider)
        response = self.client.get(self.team_url)
        self.assertContains(response, 'Add cleaner by name')
        self.assertContains(response, 'No eligible accounts available')

    def test_offline_cleaner_can_be_assigned_task(self):
        person = OfflineCleaner.objects.create(hut=self.hut, name='Maria')
        response = self._assign(f'offline:{person.pk}')
        self.assertEqual(response.status_code, 302)
        task = HousekeepingTask.objects.get(bed=self.bed)
        self.assertIsNone(task.assignee_id)
        self.assertEqual(task.offline_assignee_id, person.pk)
        self.assertContains(self.client.get(self.tasks_url), 'Maria')

    def test_switch_between_offline_registered_and_unassigned(self):
        person = OfflineCleaner.objects.create(hut=self.hut, name='Maria')
        HutCleaner.objects.create(hut=self.hut, user=self.cleaner)
        self._assign(f'offline:{person.pk}')
        self._assign(f'user:{self.cleaner.pk}')
        task = HousekeepingTask.objects.get(bed=self.bed)
        self.assertIsNone(task.offline_assignee_id)
        self.assertEqual(task.assignee_id, self.cleaner.pk)
        self._assign('')
        task.refresh_from_db()
        self.assertIsNone(task.assignee_id)
        self.assertIsNone(task.offline_assignee_id)

    def test_old_numeric_user_selection_still_works(self):
        HutCleaner.objects.create(hut=self.hut, user=self.cleaner)
        self.assertEqual(self._assign(str(self.cleaner.pk)).status_code, 302)
        self.assertEqual(HousekeepingTask.objects.get(bed=self.bed).assignee_id, self.cleaner.pk)

    def test_cross_hut_offline_assignee_is_rejected(self):
        person = OfflineCleaner.objects.create(hut=self.other_hut, name='Other Cleaner')
        response = self._assign(f'offline:{person.pk}')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(HousekeepingTask.objects.exists())

    def test_manager_cannot_remove_cleaner_from_other_hut(self):
        person = OfflineCleaner.objects.create(hut=self.other_hut, name='Other Cleaner')
        response = self.client.post(self.team_url, {
            'action': 'remove_offline', 'offline_id': person.pk,
        })
        self.assertEqual(response.status_code, 404)
        self.assertTrue(OfflineCleaner.objects.filter(pk=person.pk).exists())

    def test_removing_offline_cleaner_unassigns_without_deleting_task(self):
        person = OfflineCleaner.objects.create(hut=self.hut, name='Maria')
        self._assign(f'offline:{person.pk}')
        response = self.client.post(self.team_url, {'action': 'remove_offline', 'offline_id': person.pk})
        self.assertEqual(response.status_code, 302)
        task = HousekeepingTask.objects.get(bed=self.bed)
        self.assertIsNone(task.offline_assignee_id)
        self.assertEqual(task.status, 'open')

    def test_removing_registered_cleaner_unassigns_their_tasks(self):
        HutCleaner.objects.create(hut=self.hut, user=self.cleaner)
        self._assign(f'user:{self.cleaner.pk}')
        self.client.post(self.team_url, {'action': 'remove', 'user_id': self.cleaner.pk})
        self.assertIsNone(HousekeepingTask.objects.get(bed=self.bed).assignee_id)

    def test_cleaner_cannot_manage_team_or_assign_tasks(self):
        HutCleaner.objects.create(hut=self.hut, user=self.cleaner)
        self.client.force_login(self.cleaner)
        self.assertEqual(self.client.post(self.team_url, {'action': 'add_offline', 'name': 'Intruder'}).status_code, 403)
        self.assertEqual(self._assign('').status_code, 403)
        self.assertFalse(OfflineCleaner.objects.exists())

    def test_other_user_cannot_manage_team(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(self.team_url, {'action': 'add_offline', 'name': 'Intruder'}).status_code, 403)
        self.assertEqual(self.client.get(self.tasks_url).status_code, 403)

    def test_cleaner_cannot_complete_offline_assigned_task(self):
        person = OfflineCleaner.objects.create(hut=self.hut, name='Maria')
        self._assign(f'offline:{person.pk}')
        HutCleaner.objects.create(hut=self.hut, user=self.cleaner)
        self.client.force_login(self.cleaner)
        response = self.client.post(self.tasks_url, {
            'action': 'progress', 'bed_id': str(self.bed.pk), 'status': 'done',
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(HousekeepingTask.objects.get(bed=self.bed).status, 'open')

    def test_manager_can_record_offline_task_progress(self):
        person = OfflineCleaner.objects.create(hut=self.hut, name='Maria')
        self._assign(f'offline:{person.pk}')
        response = self.client.post(self.tasks_url, {
            'action': 'progress', 'bed_id': str(self.bed.pk), 'status': 'done',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(HousekeepingTask.objects.get(bed=self.bed).status, 'done')
