from django.contrib import admin
from django.urls import include, path
from django.views.i18n import set_language

urlpatterns = [
    path("language/", set_language, name="set_language"),
    path("admin/", admin.site.urls),
    path("", include("bookings.urls")),
    path("staff/floorplans/", include("floorplans.urls")),
]
