"""Template-level regression checks for the property hub presentation.

These tests render with sample context and do not create reservations or touch
production data. The existing view remains responsible for hut authorization.
"""
from datetime import date, timedelta
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase


class PropertyDashboardTemplateTests(SimpleTestCase):
    def setUp(self):
        self.hut = SimpleNamespace(pk=3, name='Sample Hut')
        self.request = RequestFactory().get('/staff/floorplans/3/hub/')
        self.request.user = AnonymousUser()  # Shared nav does not query DB.

    def render(self, manager):
        start = date(2026, 10, 18)
        days = [{
            'day': start + timedelta(days=i), 'occupied': 4, 'pending': 1,
            'free': 5, 'available_capacity': 10, 'over_capacity': False,
        } for i in range(7)]
        context = {
            'request': self.request, 'hut': self.hut, 'manager': manager,
            'today': start, 'occupied_beds': 5, 'capacity': 10,
            'arrivals': 2, 'departures': 1, 'counts': {'open': 1, 'in_progress': 0, 'done': 0},
            'task_total': 0, 'tasks': [], 'forecast_v38': days,
            'alert_summary_v40': {'counts': {'urgent': 0}, 'top': []},
            'v37_confirmed_beds_today': 4, 'v37_arrivals_tomorrow': 1,
            'v37_booking_value_today': 50, 'cleaner_count': 2,
        }
        return render_to_string('floorplans/staff_hub.html', context)

    def test_manager_has_property_dashboard_and_actions(self):
        html = self.render(manager=True)
        self.assertIn('PROPERTY OVERVIEW', html)
        self.assertIn('New reservation', html)
        self.assertIn('/staff/floorplans/3/new-booking/', html)
        self.assertIn('The next 7 nights', html)
        self.assertIn('Advanced reports', html)
        self.assertIn('No operations alerts', html)
        self.assertIn('SummitDesk', html)

    def test_cleaner_sees_only_housekeeping_tools(self):
        html = self.render(manager=False)
        self.assertIn('My assigned tasks', html)
        self.assertIn('My cleaning tasks', html)
        self.assertNotIn('New reservation', html)
        self.assertNotIn('Advanced reports', html)
        self.assertNotIn('Estimated booking value', html)
        self.assertNotIn('The next 7 nights', html)

    def test_advanced_reports_preserved_in_manager_template(self):
        html = self.render(manager=True)
        self.assertIn('Export 7-day forecast CSV', html)
        self.assertIn('Operations alerts', html)
        self.assertIn('Forecast capacity watch', html)
