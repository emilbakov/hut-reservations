SummitDesk v162 - reservation action button contrast

Problem: .mr-actions button makes the cancellation submit button white,
while staff_v152.css forces its text white. The label appears missing.

Fix: scoped, high-specificity CSS in manager_reservations.html restores
red cancellation and green approval buttons with visible white labels.
The cancellation endpoint and data handling are unchanged.

Installation from /home/deploy/hut-reservations:
cp bookings/templates/bookings/manager_reservations.html /home/deploy/manager_reservations.pre-v162.html
unzip -o /home/deploy/summitdesk_v162_reservation_buttons_fix.zip
myprojectenv/bin/python manage.py test bookings.test_reservations_button_v162 --settings=config.settings_test
myprojectenv/bin/python manage.py test --settings=config.settings_test
sudo systemctl restart gunicorn

No migrations or collectstatic needed; styles are inline in the template.
