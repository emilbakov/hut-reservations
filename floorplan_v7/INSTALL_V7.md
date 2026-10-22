V7 visual bed assignments
=========================

1. Copy floorplans/visual_beds.py into your existing floorplans app.
2. Copy floorplans/templates/floorplans/visual_beds.html into the same template path.
3. Add to floorplans/urls.py:

   from . import visual_beds as vb

   path('<int:hut_id>/visual-beds/', vb.visual_beds, name='visual_beds'),

4. Run python manage.py check and restart Gunicorn.
5. Visit /staff/floorplans/3/visual-beds/ (replace 3 with your hut ID).

Requires V6 bed_management routes including bed_data, assign_bed and unassign_bed.
No migrations. No existing files are replaced.

IMPORTANT: Editor bed_positions stores only x/y coordinates, not bed IDs. V7 maps
positions in saved order to numbered Bed records sorted by number. If bed numbers
are inserted/deleted/reordered or markers edited, the visual association can change.
Do not treat marker position as a durable bed identity. For durable mapping, add a
bed ID field and migration in a future version.

An unassigned bed may still be unavailable due to room-level unallocated bookings.
V6 assignment API enforces overlapping assignments, closures and room capacity.
The page does not claim that unassigned beds are free.

V7 does not provide a complete visual layout of rooms; it visualizes numbered beds
within a selected room on an 8x6 grid, based on editor marker positions.

Test on staging first. Existing V6 data endpoints expose manager-scoped guest data.
