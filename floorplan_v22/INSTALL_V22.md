# V22 housekeeping history and checkout integration

Prerequisites: V13 arrivals and V21 housekeeping installed; PostgreSQL configured.

## Files
Copy `housekeeping_events.py`, `checkout_cleaning.py` to `floorplans/`.
Copy `staff_housekeeping_v22.py` to `floorplans/` **as** `staff_housekeeping.py`.
Copy template to `floorplans/templates/floorplans/staff_housekeeping.html`.

At bottom of `floorplans/models.py` add:
```python
from .housekeeping_events import BedCleaningEvent
```
Keep V21's `from .housekeeping_models import BedHousekeeping` intact.

## Checkout hook (required for automatic dirty status)
In `floorplans/staff_arrivals.py`, add import:
```python
from .checkout_cleaning import mark_checkout_beds_dirty
```
In the successful checkout branch, immediately **after**:
```python
stay.save(update_fields=['checked_out_at', 'checked_out_by'])
```
add (at the same indentation level):
```python
mark_checkout_beds_dirty(reservation, request.user)
```
Do not call for check-in, failed checkout, or already-checked-out reservations.
The hook is called inside V13's existing transaction; failure rolls back checkout.

**Limitation:** Only explicitly assigned numbered beds are auto-marked dirty.
Room-level reservations without BedAssignment records cannot be safely mapped to
physical beds. The board shows such beds as unverified rather than assuming free.
Checkout does not change maintenance closures or reservation dates/status.

## Migration and deploy
Back up PostgreSQL before changing files.
Use production settings and environment:
```bash
cd /home/deploy/hut-reservations
source myprojectenv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_postgres
set -a
source /etc/hut-reservations/postgres.env
set +a
python manage.py makemigrations floorplans
python manage.py migrate floorplans
python manage.py check
sudo systemctl restart gunicorn.service
```
Ensure migration creates BedCleaningEvent and does not delete any model.

## Test
1. Mark a bed ready and verify a history event.
2. Use a test confirmed reservation with an assigned numbered bed, check it in and out via V13.
3. Verify its assigned bed becomes Needs Cleaning and a Checkout history event appears.
4. Verify another unassigned bed was not changed.
