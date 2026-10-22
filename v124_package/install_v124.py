#!/usr/bin/env python3
"""Install public homepage + hut directory, preserving staff and booking flows.

Run from Django project root. No migrations. Refuses unexpected URLs and
existing target files. A timestamped backup and manifest allow rollback.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import tempfile

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent
URLS = "bookings/urls.py"
FILES = {
    "bookings/public_site_v124.py": "public_site_v124.py",
    "bookings/templates/bookings/public_base_v124.html": "public_base_v124.html",
    "bookings/templates/bookings/public_home_v124.html": "public_home_v124.html",
    "bookings/templates/bookings/public_directory_v124.html": "public_directory_v124.html",
    "bookings/templates/bookings/public_search_v124.html": "public_search_v124.html",
    "bookings/templates/bookings/public_cards_v124.html": "public_cards_v124.html",
    "bookings/static/bookings/public_v124.css": "public_v124.css",
    "bookings/test_public_site_v124.py": "test_public_site_v124.py",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def atomic_write(target, data):
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent, prefix=".sd124_", delete=False) as fh:
            tmp = Path(fh.name)
            fh.write(data)
        os.chmod(tmp, (target.stat().st_mode & 0o777) if target.exists() else 0o644)
        os.replace(tmp, target)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def patch_urls(source):
    import_line = "from . import views\n"
    require(source.count(import_line) == 1, "Cannot locate views import in bookings/urls.py")
    source = source.replace(import_line, import_line + "from . import public_site_v124\n", 1)
    original = ('    path("", views.role_landing, name="role_landing"),\n'
                '    path("huts/", views.hut_list, name="hut_list"),')
    replacement = ('    path("", public_site_v124.public_home, name="public_home"),\n'
                   '    path("welcome/", views.role_landing, name="role_landing"),\n'
                   '    path("huts/", public_site_v124.public_huts, name="hut_list"),')
    require(source.count(original) == 1, "Public URL configuration differs from expected source; nothing changed.")
    return source.replace(original, replacement, 1)


def validate_path(relative):
    target = ROOT / relative
    require(not target.is_symlink(), f"Refusing symlink: {relative}")
    parent = target.parent
    while parent != ROOT:
        require(not parent.is_symlink(), f"Refusing symlink directory: {parent}")
        require(ROOT in parent.parents, f"Path escapes project: {relative}")
        parent = parent.parent
    return target


def main():
    require((ROOT / "manage.py").is_file(), "Run from the SummitDesk Django project root.")
    require((ROOT / "bookings/models.py").is_file(), "Cannot find bookings app.")
    require((ROOT / "bookings/staff_auth_v117.py").is_file(), "Install staff login (v117) first.")
    require((ROOT / "bookings/static/bookings/adventure-hero.avif").is_file(),
            "Existing public hero image is missing. No changes made.")
    target_urls = validate_path(URLS)
    require(target_urls.is_file(), "Missing bookings/urls.py")
    old_urls = target_urls.read_text(encoding="utf-8")
    new_urls = patch_urls(old_urls).encode("utf-8")
    payload = {URLS: new_urls}
    for rel, filename in FILES.items():
        dest = validate_path(rel)
        require(not dest.exists(), f"Already installed or conflicting file: {rel}")
        src = PACKAGE / filename
        require(src.is_file() and not src.is_symlink(), f"Missing package file: {filename}")
        payload[rel] = src.read_bytes()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup = ROOT / "summitdesk_backups" / f"public_site_{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    manifest = [{"path": rel, "existed": (ROOT / rel).is_file()} for rel in payload]
    for entry in manifest:
        if entry["existed"]:
            destination = backup / entry["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / entry["path"], destination)
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    try:
        for rel, data in payload.items():
            atomic_write(ROOT / rel, data)
    except Exception:
        for entry in manifest:
            dest = ROOT / entry["path"]
            if entry["existed"]:
                shutil.copy2(backup / entry["path"], dest)
            else:
                dest.unlink(missing_ok=True)
        raise
    print("Public homepage and hut directory installed.")
    print("Backup:", backup)
    print("No database migration required. Run Django checks before restarting Gunicorn.")


if __name__ == "__main__":
    main()
