ADVENTURE DESIGN PATCH — Django hut-reservations

Files included:
- bookings/templates/bookings/base.html
- bookings/templates/bookings/hut_list.html
- bookings/static/bookings/site.css
- bookings/static/bookings/adventure-hero.avif (existing project photo)

The design leaves booking views, database, models, and URLs untouched.

INSTALL (test locally/staging first):
1. Back up your current base.html, hut_list.html and site.css.
2. Unzip into your Django project root, preserving folders.
3. Run: python manage.py collectstatic --noinput --settings=config.settings_postgres
   (Use your configured environment variables for production.)
4. Restart Gunicorn only if needed; refresh browser (Ctrl+F5).

No new Python dependencies. Fonts load from Google Fonts and fall back to system fonts.
The hero image uses one existing uploaded hut photograph; replace it with your preferred landscape image if desired.
