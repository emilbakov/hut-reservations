#!/usr/bin/env python3
"""Install one public hut detail redesign; preserve the booking service.

Run from the Django project root after v124. Creates timestamped backups
and refuses unexpected view code, symlinks or pre-existing payload files.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import tempfile

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent
VIEWS = "bookings/views.py"
FILES = {
    "bookings/templates/bookings/public_hut_v125.html": "public_hut_v125.html",
    "bookings/static/bookings/public_hut_v125.css": "public_hut_v125.css",
    "bookings/static/bookings/public_hut_v125.js": "public_hut_v125.js",
    "bookings/test_public_hut_v125.py": "test_public_hut_v125.py",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def safe_target(relative):
    target = ROOT / relative
    require(not target.is_symlink(), f"Refusing symlink: {relative}")
    parent = target.parent
    while parent != ROOT:
        require(ROOT in parent.parents, f"Path escapes project: {relative}")
        require(not parent.is_symlink(), f"Refusing symlink directory: {parent}")
        parent = parent.parent
    return target


def patch_views(source):
    replacements = [
        ('    return book(request, hut=hut)\n',
         '    return book(request, hut=hut, template_name="bookings/public_hut_v125.html")\n'),
        ('def book(request, hut=None):\n',
         'def book(request, hut=None, *, template_name="bookings/book.html"):\n'),
        ('    context = {\n        "search": search,\n        "hut": hut,\n    }\n',
         '    context = {\n        "search": search,\n        "hut": hut,\n    }\n'
         '    if hut is not None:\n'
         '        context["public_rooms"] = Room.objects.filter(hut=hut, is_active=True).order_by("position", "name")\n'),
        ('    return render(request, "bookings/book.html", context)\n',
         '    return render(request, template_name, context)\n'),
    ]
    for old, new in replacements:
        require(source.count(old) == 1, f"Booking view differs from expected source: {old.strip()}. No changes made.")
        source = source.replace(old, new, 1)
    return source


def atomic_write(target, data):
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent, prefix=".sd125_", delete=False) as handle:
            temp = Path(handle.name)
            handle.write(data)
        os.chmod(temp, (target.stat().st_mode & 0o777) if target.exists() else 0o644)
        os.replace(temp, target)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    require((ROOT / "manage.py").is_file(), "Run from the SummitDesk project root.")
    require((ROOT / "bookings/templates/bookings/public_base_v124.html").is_file(), "Install v124 first: public base missing.")
    require((ROOT / "bookings/static/bookings/public_v124.css").is_file(), "Install v124 first: public stylesheet missing.")
    urls = (ROOT / "bookings/urls.py").read_text(encoding="utf-8")
    require('name="public_home"' in urls and 'name="hut_detail"' in urls,
            "Public routes from v124 are missing.")
    views = safe_target(VIEWS)
    require(views.is_file(), "Missing bookings/views.py")
    old = views.read_text(encoding="utf-8")
    payload = {VIEWS: patch_views(old).encode("utf-8")}
    for rel, filename in FILES.items():
        target = safe_target(rel)
        require(not target.exists(), f"Already installed or conflicting file: {rel}")
        src = PACKAGE / filename
        require(src.is_file() and not src.is_symlink(), f"Missing package file: {filename}")
        payload[rel] = src.read_bytes()

    # Validate the patched Python before writing any file.
    compile(payload[VIEWS], VIEWS, "exec")
    compile(payload["bookings/test_public_hut_v125.py"], "test_public_hut_v125.py", "exec")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup = ROOT / "summitdesk_backups" / f"public_hut_{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    manifest = [{"path": rel, "existed": safe_target(rel).is_file()} for rel in payload]
    for entry in manifest:
        if entry["existed"]:
            destination = backup / entry["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / entry["path"], destination)
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    try:
        for rel, data in payload.items():
            atomic_write(safe_target(rel), data)
    except Exception:
        for entry in manifest:
            target = safe_target(entry["path"])
            if entry["existed"]:
                shutil.copy2(backup / entry["path"], target)
            else:
                target.unlink(missing_ok=True)
        raise
    print("Public hut details installed. Existing booking logic unchanged.")
    print("Backup:", backup)
    print("No database migrations required. Run Django checks before restarting.")


if __name__ == "__main__":
    main()
