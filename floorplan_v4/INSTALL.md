# Visual Availability Map V4

This package preserves your uploaded V3 editor and views, adds a separate availability map, and fixes availability date checking to use timezone.localdate().

1. Back up floorplans/views.py, floorplans/urls.py and floorplans/templates/floorplans/editor.html.
2. Copy floorplans/views.py to your project floorplans/views.py.
3. Copy floorplans/templates/floorplans/editor.html to your project floorplans/templates/floorplans/editor.html.
4. Copy floorplans/templates/floorplans/availability_map.html to your project floorplans/templates/floorplans/availability_map.html.
5. In floorplans/urls.py add to urlpatterns:
   path("<int:hut_id>/availability-map/", views.availability_map, name="availability_map"),
   Keep all existing URL routes. Ensure `from . import views` and `from django.urls import path` are present.
6. Run `python manage.py check`, then restart your actual Gunicorn service.
7. Open /staff/floorplans/<hut_id>/availability-map/ or use "View availability" from editor.

No new migrations required. Does not assign individual beds. The booking link passes dates to the existing manual booking page, but that page must already support query-string date prefill for those dates to be populated automatically.

Note: The availability endpoint uses BOOKING_MAX_DAYS_AHEAD and BOOKING_MAX_NIGHTS settings already present in your uploaded views.py. Test with your real Django settings.
