
from django.urls import path

from . import views
from . import public_site_v124
from . import approval_dashboard_v127
from .staff_auth_v117 import StaffLoginView, StaffLogoutView

app_name = "bookings"

urlpatterns = [
    path("staff/login/", StaffLoginView.as_view(), name="staff_login"),
    path("staff/logout/", StaffLogoutView.as_view(), name="staff_logout"),
    # Public role selection and preserved hut directory
    path("", public_site_v124.public_home, name="public_home"),
    path("welcome/", views.role_landing, name="role_landing"),
    path("huts/", public_site_v124.public_huts, name="hut_list"),

    # Booking page for a specific hut
    path("huts/<slug:slug>/", views.hut_detail, name="hut_detail"),

    # Existing booking view (temporary legacy URL)
    path("book/", views.book, name="book"),

    # Availability calendar
    path(
        "availability/calendar/",
        views.availability_calendar,
        name="calendar",
    ),

    # Reservation management
    path(
        "r/<str:code>/modify/",
        views.reservation_modify,
        name="modify",
    ),
    path(
        "r/<str:code>/",
        views.reservation_detail,
        name="reservation",
    ),
    path(
        "r/<str:code>/cancel/",
        views.reservation_cancel,
        name="cancel",
    ),

    # Guest requests approval dashboard
    path("staff/reservations/requests/", approval_dashboard_v127.approval_dashboard, name="approval_dashboard"),

    # Hut manager reservation management
    path("staff/reservations/", views.manager_reservations, name="manager_reservations"),
    path("staff/reservations/<str:code>/action/", views.manager_reservation_action, name="manager_reservation_action"),

    # Manager arrivals, departures, and actual stay events
    path("staff/stays/", views.manager_stays, name="manager_stays"),
    path("staff/stays/<str:code>/action/", views.manager_stay_action, name="manager_stay_action"),

    # Staff dashboard
    path(
        "staff/dashboard/",
        views.dashboard,
        name="dashboard",
    ),
    path(
        "staff/dashboard/export/",
        views.dashboard_export,
        name="dashboard_export",
    ),
]

# Guest stay history and reports
from . import reports
urlpatterns += [
    path("staff/history/", reports.stay_history, name="stay_history"),
    path("staff/history/export/", reports.stay_history_export, name="stay_history_export"),
]

# Annual hut performance report
from . import yearly_reports
urlpatterns += [
    path("staff/performance/", yearly_reports.yearly_performance, name="yearly_performance"),
    path("staff/performance/export/", yearly_reports.yearly_performance_export, name="yearly_performance_export"),
]

# Staff manual reservations
from . import manual_bookings
urlpatterns += [
    path("staff/reservations/new/", manual_bookings.manual_booking, name="manual_booking"),
]

# Manager room availability calendar
from . import room_calendar
urlpatterns += [
    path("staff/rooms/calendar/", room_calendar.room_calendar, name="room_calendar"),
]

# Individual bed management
from .bed_management import bed_management
urlpatterns += [
    path('staff/rooms/<int:room_id>/beds/', bed_management, name='bed_management'),
]

# Staff manual payment ledger
from .payments import reservation_payments
urlpatterns += [
    path('staff/reservations/<str:code>/payments/', reservation_payments, name='reservation_payments'),
]

# Financial dashboard and CSV export
from .financial_reports import financial_dashboard, financial_export
urlpatterns += [
    path('staff/finances/', financial_dashboard, name='financial_dashboard'),
    path('staff/finances/export/', financial_export, name='financial_export'),
]

# Hut expense management and CSV export
from .expenses import expense_dashboard, expense_export
urlpatterns += [
    path('staff/expenses/', expense_dashboard, name='expense_dashboard'),
    path('staff/expenses/export/', expense_export, name='expense_export'),
]

# Deposit policies, deadlines and overdue tracking
from .deposits import deposit_dashboard
urlpatterns += [
    path('staff/deposits/', deposit_dashboard, name='deposit_dashboard'),
]

# Reservation deposit lifecycle
from .lifecycle import lifecycle_dashboard
urlpatterns += [
    path('staff/deposits/lifecycle/', lifecycle_dashboard, name='lifecycle_dashboard'),
]

from .communications import communications_dashboard
urlpatterns += [
    path('staff/communications/', communications_dashboard, name='communications_dashboard'),
]

from .self_service import guest_self_service, guest_requests_dashboard
urlpatterns += [
    path('guest/manage/<str:token>/', guest_self_service, name='guest_self_service'),
    path('staff/guest-requests/', guest_requests_dashboard, name='guest_requests_dashboard'),
]

from .guest_links import guest_link_controls
urlpatterns += [
    path('staff/guest-links/', guest_link_controls, name='guest_link_controls'),
]

from .availability_calendar import availability_calendar
urlpatterns += [
    path('staff/availability/', availability_calendar, name='availability_calendar'),
]

from .calendar_actions import calendar_create, calendar_edit
urlpatterns += [
    path('staff/availability/new/', calendar_create, name='calendar_create'),
    path('staff/availability/edit/<str:code>/', calendar_edit, name='calendar_edit'),
]

from .calendar_timeline import calendar_timeline
from .calendar_drag import calendar_move
urlpatterns += [
    path('staff/availability/week/', calendar_timeline, name='calendar_timeline'),
    path('staff/availability/move/', calendar_move, name='calendar_move'),
]
