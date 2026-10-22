#!/usr/bin/env python3
"""Restore a v135 dashboard backup after checking installed file hashes.

Run from project root: python3 v135_package/rollback_v135.py summitdesk_backups/dashboard_v135_TIMESTAMP
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path.cwd().resolve()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(target, data):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".sd135_rollback_", delete=False) as fh:
            tmp = Path(fh.name)
            fh.write(data)
        os.chmod(tmp, target.stat().st_mode & 0o777 if target.exists() else 0o644)
        os.replace(tmp, target)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup_dir", help="Exact v135 backup folder printed by installer")
    args = parser.parse_args()
    backup = (ROOT / args.backup_dir).resolve()
    backup_root = (ROOT / "summitdesk_backups").resolve()
    if backup.parent != backup_root or not backup.name.startswith("dashboard_v135_"):
        raise RuntimeError("Backup must be a direct dashboard_v135_* child of summitdesk_backups.")
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != "v135":
        raise RuntimeError("Invalid v135 manifest.")
    expected_paths = {"bookings/templates/bookings/dashboard.html", "bookings/test_dashboard_ui_v135.py"}
    if set(manifest["installed"]) != expected_paths or set(manifest["originals"]) != {"bookings/templates/bookings/dashboard.html"}:
        raise RuntimeError("Unexpected manifest file list.")
    for rel, expected in manifest["installed"].items():
        path = ROOT / rel
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError(f"Refusing rollback: {rel} was modified after installation.")
    original_rel = "bookings/templates/bookings/dashboard.html"
    saved = backup / original_rel
    if saved.is_symlink() or not saved.is_file() or sha(saved.read_bytes()) != manifest["originals"][original_rel]:
        raise RuntimeError("Backup is missing or damaged.")
    atomic_write(ROOT / original_rel, saved.read_bytes())
    (ROOT / "bookings/test_dashboard_ui_v135.py").unlink()
    print("Restored original dashboard; removed v135 test. No database changes.")


if __name__ == "__main__":
    main()
