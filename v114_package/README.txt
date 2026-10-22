SummitDesk v114 — Reservation Quick View
=========================================
Prerequisite: v113 reservation timeline is installed.

What changes
- Clicking a booking opens a polished accessible details drawer.
- Displays code, guest, confirmation status, room, hut, check-in,
  check-out, booked beds in that room, and nights.
- Edit Reservation uses the EXACT existing booking edit link.
- Original drag/drop move-confirmation workflow remains unchanged.
- Close with X, Back to calendar, or Escape; calendar stays visible.
- Ctrl/Cmd+Click still opens the edit link in a separate tab.
- No JavaScript? The original booking edit links continue to work.
- No database migrations or new server endpoints, and no website
  version labels.

Upload from Windows PowerShell
  scp "$env:USERPROFILE\Downloads\summitdesk_v114.zip" deploy@167.233.96.3:/home/deploy/hut-reservations/

Install on Ubuntu
  cd /home/deploy/hut-reservations
  unzip -o summitdesk_v114.zip
  python3 v114_package/install_v114.py

Verify (with your existing activated virtualenv and environment)
  python manage.py check
  sudo systemctl restart gunicorn.service

Test
  /staff/availability/week/
  1. Click a confirmed or pending booking: quick view opens.
  2. Check dates, room, hut, and beds against actual reservation.
  3. Click Edit reservation: existing edit form opens.
  4. Reopen then press Escape / Back to calendar: drawer closes.
  5. Drag booking to another night: existing move confirmation opens.
  6. Test touch and keyboard operation on phone/desktop.
  7. Confirm staff/hut permissions remain unchanged.

Rollback: copy the timestamped .bak_v114_... template back over
bookings/templates/bookings/calendar_timeline.html, then restart gunicorn.
