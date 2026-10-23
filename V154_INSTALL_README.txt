SUMMITDESK v154 — KARLAK NAVIGATION PATCH
=========================================
A small PATCH ZIP intended for the existing v153 installation.

Changes:
- Removes all CSS backgrounds, rounded badges, and shadows from the logo in
  the public navbar, legacy navbar and staff sidebar.
- Makes navbar logos 72px (58px on narrow public screens).
- Replaces navigation brand text with "Karlak" on public and staff pages.
- Adds a versioned stylesheet to avoid old browser CSS caches.
- Keeps the original v153 transparent logo files, booking logic and database.
- Adds two small regression checks. No migrations needed.

Windows PowerShell:
  scp "$env:USERPROFILE\Downloads\summitdesk_v154_karlak_nav.zip" deploy@167.233.96.3:/home/deploy/
  ssh deploy@167.233.96.3

Ubuntu Bash (after backup):
  cd /home/deploy/hut-reservations
  unzip -o /home/deploy/summitdesk_v154_karlak_nav.zip
  source myprojectenv/bin/activate
  python manage.py test --settings=config.settings_test

Collectstatic with the existing production environment (DO NOT print secrets):
  sudo bash -c '
  set -a
  source /etc/hut-reservations/postgres.env
  set +a
  cd /home/deploy/hut-reservations
  runuser -u deploy -- myprojectenv/bin/python manage.py collectstatic --noinput
  '

Restart only after tests and collectstatic succeed:
  sudo systemctl restart gunicorn
  sudo systemctl status gunicorn --no-pager

Hard refresh the public navbar and staff sidebar (Ctrl+Shift+R).
