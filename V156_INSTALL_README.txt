SUMMITDESK v156 — KARLAK LINKS ON THE RIGHT
=============================================
Patch for an existing v154/v155 installation. No migrations.

Changes:
- Public desktop navbar links are right-aligned (logo remains on the left).
- Footer Useful links move to the rightmost column; brand stays on the left.
- Footer links are right-aligned on desktop and mobile.
- Supports sites with or without the optional v155 left-links patch.
- Does not change the staff sidebar or reservation logic.

1. WINDOWS POWERSHELL
scp "$env:USERPROFILE\Downloads\summitdesk_v156_right_links.zip" deploy@167.233.96.3:/home/deploy/
ssh deploy@167.233.96.3

2. UBUNTU BASH — BACKUP & INSTALL
cd /home/deploy
tar -czf hut-reservations-backup-before-v156.tar.gz --exclude=myprojectenv --exclude=.git --exclude=staticfiles hut-reservations
cd /home/deploy/hut-reservations
unzip -o /home/deploy/summitdesk_v156_right_links.zip
source myprojectenv/bin/activate

3. TEST
python manage.py test --settings=config.settings_test

4. COLLECTSTATIC — EXISTING PRODUCTION ENVIRONMENT
sudo bash -c '
set -a
source /etc/hut-reservations/postgres.env
set +a
cd /home/deploy/hut-reservations
runuser -u deploy -- myprojectenv/bin/python manage.py collectstatic --noinput
'

5. RESTART GUNICORN (only after tests and collectstatic succeed)
sudo systemctl restart gunicorn
sudo systemctl status gunicorn --no-pager

6. HARD REFRESH (CTRL+SHIFT+R)
Verify public desktop navbar links and footer Useful links appear on the right.
