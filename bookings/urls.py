from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.book, name="book"),
    path("availability/calendar/", views.availability_calendar, name="calendar"),
    path("r/<str:code>/modify/", views.reservation_modify, name="modify"),
    path("staff/dashboard/", views.dashboard, name="dashboard"),
    path("staff/dashboard/export/", views.dashboard_export, name="dashboard_export"),
    path("r/<str:code>/", views.reservation_detail, name="reservation"),
    path("r/<str:code>/cancel/", views.reservation_cancel, name="cancel"),
]
