#!/usr/bin/env python3
"""Restore a v125 backup from the Django project root.

Usage: python3 v125_package/rollback_v125.py summitdesk_backups/public_hut_TIMESTAMP
"""
from pathlib import Path
import json
import shutil
import sys

ROOT = Path.cwd().resolve()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 v125_package/rollback_v125.py summitdesk_backups/public_hut_TIMESTAMP")
    backups_root = (ROOT / "summitdesk_backups").resolve()
    backup = (ROOT / sys.argv[1]).resolve()
    if backup.parent != backups_root or not backup.name.startswith("public_hut_"):
        raise RuntimeError("Provide an exact public_hut_ backup directory under summitdesk_backups.")
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest:
        rel = Path(entry["path"])
        if rel.is_absolute() or ".." in rel.parts or (ROOT / rel).is_symlink():
            raise RuntimeError(f"Unsafe path: {rel}")
        if entry["existed"] and not (backup / rel).is_file():
            raise RuntimeError(f"Missing backup: {rel}")
    for entry in manifest:
        rel = Path(entry["path"])
        target = ROOT / rel
        if entry["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup / rel, target)
        else:
            target.unlink(missing_ok=True)
    print("Restored files from:", backup)
    print("Run python manage.py check and restart Gunicorn.")


if __name__ == "__main__":
    main()
