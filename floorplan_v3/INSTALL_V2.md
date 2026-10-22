# Floor plan editor v2 — upgrade

This ZIP includes the complete `floorplans/` app (v1 plus v2), and the unchanged booking template. **If v1 is already installed, do not replace the booking template or the existing `floorplans/migrations/0001_initial.py` with a different version.**

1. Back up the database and existing `floorplans/` directory.
2. Replace the Python files and editor template in `floorplans/`; add migration `0002_floorfeature.py`.
3. Run `python manage.py showmigrations floorplans`, `python manage.py makemigrations --check --dry-run floorplans`, `python manage.py migrate floorplans`, `python manage.py check` with the active settings/database environment.
4. Restart Gunicorn only if checks pass.

New features: draggable stairs, corridors, doors; resize existing room rectangles by dragging their lower-right handle; server-side validation of feature type and bounds. Rooms still cannot overlap other rooms. Architectural features are **visual markers only**, and may overlap rooms/each other (e.g. a door on a room boundary). Floor plan does not change booking availability or prices. Features are saved together with room placements; saving replaces the hut's existing feature markers.

Important: If your earlier v1 was not installed, first follow INSTALL.md and confirm the bookings migration dependency in 0001.
