SummitDesk Calendar — Available Rooms Filter v3

This upgrade modifies only:
  floorplans/templates/floorplans/property_calendar_v138.html
  floorplans/static/floorplans/property_planner_v147.js
and creates:
  floorplans/static/floorplans/property_available_filter_v3.css

The installer patches the existing files instead of replacing them. It refuses to proceed if its expected anchors do not match. Before writing, it backs up the existing HTML and JavaScript in a timestamped directory in the project root.

Feature: select arrival, departure, and beds, then enable "Available rooms only". Rooms that cannot accommodate all selected nights are hidden. The currently selected room stays visible to permit corrections. The room selector filter continues to work. This is display-only; the server validates bookings.

INSTALL (run from project root):
  unzip -o summitdesk_calendar_available_rooms_v3.zip
  myprojectenv/bin/python install_calendar_filter_v3.py
  node --check floorplans/static/floorplans/property_planner_v147.js
  sudo systemctl restart gunicorn

Run Django checks and collectstatic using your usual production environment before restarting.
