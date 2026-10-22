# V6 individual bed assignment (additive installation)

This ZIP intentionally DOES NOT replace bookings/services.py, bookings/models.py, floorplans/views.py, or your existing floorplan templates. No migrations required if Bed, BedAssignment and BedClosure are already migrated.

1. Back up code and database before deploying.
2. Copy `floorplans/bed_management.py` to your existing `floorplans/` app.
3. Copy `floorplans/templates/floorplans/bed_manager.html` to the same path in your app.
4. In `floorplans/urls.py`, add `from . import bed_management as bm` and add these patterns inside the existing urlpatterns:

    path('<int:hut_id>/beds/', bm.bed_manager, name='bed_manager'),
    path('<int:hut_id>/rooms/<int:room_id>/beds/data/', bm.bed_data, name='bed_data'),
    path('<int:hut_id>/rooms/<int:room_id>/beds/initialize/', bm.initialize_beds, name='initialize_beds'),
    path('<int:hut_id>/rooms/<int:room_id>/beds/assign/', bm.assign_bed, name='assign_bed'),
    path('<int:hut_id>/rooms/<int:room_id>/beds/unassign/', bm.unassign_bed, name='unassign_bed'),
    path('<int:hut_id>/rooms/<int:room_id>/beds/close/', bm.close_bed, name='close_bed'),
    path('<int:hut_id>/rooms/<int:room_id>/beds/reopen/', bm.reopen_bed, name='reopen_bed'),

5. Run `python manage.py check`, then restart the actual Gunicorn systemd unit.
6. Open `/staff/floorplans/<hut_id>/beds/`.

CAUTION: Existing quantity-based bookings are NOT automatically mapped to individual beds. Do not interpret blank beds as available. This screen assigns a specific numbered bed to an existing reservation item; it does not create reservations or change booked quantities. Room row locking prevents concurrent changes made through this interface, but edits made directly in Django admin or other code paths may bypass these locks. For complete concurrency guarantees, all bed/closure modification paths must use the same room lock. Test on staging first.

A bed closure is rejected if it overlaps an existing specific assignment or if the room would exceed its remaining nightly capacity. Bed closures use [start,end) dates. Existing closure records can be removed from the panel.
