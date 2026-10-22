#!/usr/bin/env python3
"""Restore a v124 backup; run from the Django project root.

Usage: python3 v124_package/rollback_v124.py summitdesk_backups/public_site_TIMESTAMP
"""
from pathlib import Path
import json
import shutil
import sys

ROOT = Path.cwd().resolve()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 v124_package/rollback_v124.py summitdesk_backups/public_site_TIMESTAMP")
    backup = (ROOT / sys.argv[1]).resolve()
    backups_root = (ROOT / "summitdesk_backups").resolve()
    if backup.parent != backups_root or not backup.name.startswith("public_site_"):
        raise SystemExit("Provide an exact public_site_ backup directory under summitdesk_backups.")
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest:
        rel = Path(item["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise RuntimeError("Unsafe manifest path")
        target = ROOT / rel
        if target.is_symlink():
            raise RuntimeError(f"Refusing symlink: {rel}")
        if item["existed"] and not (backup / rel).is_file():
            raise RuntimeError(f"Missing backup: {rel}")
    for item in manifest:
        rel = Path(item["path"])
        target = ROOT / rel
        if item["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup / rel, target)
        else:
            target.unlink(missing_ok=True)
    print("Restored files from:", backup)
    print("Run python manage.py check and restart Gunicorn.")


if __name__ == "__main__":
    main()
