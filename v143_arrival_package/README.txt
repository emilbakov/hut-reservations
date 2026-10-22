SummitDesk v143 - Arrival Date Highlight

Requires v142 Property Calendar already installed (exact template checksum).

What changes:
- After clicking an arrival date, that room/date cell remains distinctly green.
- Right-hand sidebar prompts: "Arrival selected: ... Now click a later departure date in the same room."
- Stay summary displays the selected arrival while departure is pending.
- Confirm remains disabled until departure is chosen and validation succeeds.
- Full selected stay remains green after departure selection.
- No changes to booking backend, date range, reservation bars or weekly calendar.

Install (run from project root):
  python3 v143_arrival_package/install_v143_arrival.py --check
  python3 v143_arrival_package/install_v143_arrival.py

Rollback (use backup path printed during installation):
  python3 v143_arrival_package/rollback_v143_arrival.py --list
  python3 v143_arrival_package/rollback_v143_arrival.py --check BACKUP_PATH
  python3 v143_arrival_package/rollback_v143_arrival.py BACKUP_PATH

Template-only change. No migrations, no restart required under typical Django template loading.
