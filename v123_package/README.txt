SummitDesk — Cleaning Team: name-only cleaners (v123)

FIX
- The Add Cleaner form no longer requires a pre-existing account.
- Managers may add a cleaner by name, without creating a login.
- Managers may assign daily bed-cleaning tasks to that name-only cleaner.
- Managers can record the task status for them.
- Registered cleaners can still be added and update their own tasks.
- Cleaner access stays hut-scoped; name-only cleaners have no login/access.
- Removing a cleaner leaves the task intact but unassigned.

REQUIRES ONE MIGRATION
Adds floorplans.OfflineCleaner and nullable HousekeepingTask.offline_assignee.
Does not modify reservations, beds, or existing cleaning task data.

INSTALL (run from /home/deploy/hut-reservations)
1. unzip -o summitdesk_v123.zip
2. python3 v123_package/install_v123.py
3. source myprojectenv/bin/activate
4. export DJANGO_SETTINGS_MODULE=config.settings_postgres
5. set -a; source /etc/hut-reservations/postgres.env; set +a
6. python manage.py check
7. python manage.py migrate floorplans
8. python manage.py test floorplans.test_cleaning_team_v123
9. sudo systemctl restart gunicorn.service

TEST
Open /staff/floorplans/2/cleaning-team/
- Add a cleaner by name, e.g. Maria, and verify the team list.
- Open /staff/floorplans/2/cleaning-tasks/ and assign a bed to Maria.
- Confirm a manager can update the task status.
- Confirm the name-only cleaner does not receive a login.

BACKUP / ROLLBACK
Original files are backed up in summitdesk_backups/cleaning_team_TIMESTAMP.
To restore previous UI/handlers without deleting the new data:
python3 v123_package/rollback_v123.py summitdesk_backups/cleaning_team_TIMESTAMP
This intentionally retains the model and migration to avoid losing assignments.

LIVE SERVER TESTS MUST BE RUN BY THE USER.
