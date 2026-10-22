#!/usr/bin/env python3
"""Install SummitDesk v135 staff dashboard UI (no migrations or DB writes).

Run from the project root: python3 v135_package/install_v135.py
Use --check to validate the live files without modifying anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
PKG = Path(__file__).resolve().parent
DASHBOARD = "bookings/templates/bookings/dashboard.html"
TEST_FILE = "bookings/test_dashboard_ui_v135.py"
# Snapshot of the dashboard supplied by the user, with v133 mobile changes.
EXPECTED_DASHBOARD_SHA256 = "8829ad2317f1686540d38c4f9ceee5f723ae961b8c5ed64948ac81c38817db85"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def safe_target(relative: str) -> Path:
    part = Path(relative)
    require(not part.is_absolute() and ".." not in part.parts, f"Unsafe path: {relative}")
    target = ROOT / part
    require(ROOT in target.parents and not target.is_symlink(), f"Unsafe target: {relative}")
    parent = target.parent
    while parent != ROOT:
        require(not parent.is_symlink(), f"Symlink directory refused: {parent}")
        parent = parent.parent
    return target


def atomic_write(target: Path, data: bytes) -> None:
    temporary = None
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".sd135_", delete=False) as fh:
            temporary = Path(fh.name)
            fh.write(data)
        os.chmod(temporary, target.stat().st_mode & 0o777 if target.exists() else 0o644)
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def preflight() -> tuple[dict[str, bytes], dict[str, bytes]]:
    require((ROOT / "manage.py").is_file(), "Run from the Django project root beside manage.py.")
    require((ROOT / "bookings/test_mobile_v133.py").is_file(), "v133 mobile update is required.")
    original = safe_target(DASHBOARD)
    test_target = safe_target(TEST_FILE)
    require(original.is_file(), f"Missing required file: {DASHBOARD}")
    require(not test_target.exists(), f"{TEST_FILE} already exists; refusing overwrite.")
    before = original.read_bytes()
    require(sha256(before) == EXPECTED_DASHBOARD_SHA256,
            "Dashboard differs from the supplied project snapshot. Refusing to overwrite customized changes. "
            f"Current SHA256: {sha256(before)}")
    updated = (PKG / "dashboard_v135.html").read_bytes()
    test_code = (PKG / "test_dashboard_ui_v135.py").read_bytes()
    require(b"SummitDesk v135" in updated and b"/* v133:" in updated,
            "v135 template missing expected markers.")
    compile(test_code, TEST_FILE, "exec")
    return {DASHBOARD: before}, {DASHBOARD: updated, TEST_FILE: test_code}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate only; do not change files.")
    args = parser.parse_args()
    originals, updates = preflight()
    print("SummitDesk v135 preflight OK")
    print("Dashboard baseline SHA256:", sha256(originals[DASHBOARD]))
    if args.check:
        print("Check-only mode: no files changed.")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup = ROOT / "summitdesk_backups" / f"dashboard_v135_{stamp}"
    require(not backup.exists(), "Backup destination already exists.")
    backup.mkdir(parents=True)
    for rel, data in originals.items():
        target = backup / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(safe_target(rel), target)
        require(target.read_bytes() == data, f"Backup verification failed for {rel}")

    manifest = {
        "version": "v135",
        "originals": {rel: sha256(data) for rel, data in originals.items()},
        "installed": {rel: sha256(data) for rel, data in updates.items()},
        "created": [TEST_FILE],
    }
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    written = []
    try:
        for rel, data in updates.items():
            atomic_write(safe_target(rel), data)
            written.append(rel)
            require(safe_target(rel).read_bytes() == data, f"Verification failed: {rel}")
    except Exception:
        for rel in reversed(written):
            if rel in originals:
                atomic_write(safe_target(rel), originals[rel])
            else:
                safe_target(rel).unlink(missing_ok=True)
        raise
    print("Installed SummitDesk v135 dashboard UI.")
    print("Backup:", backup)
    print("No migrations, settings, navigation or booking logic changed.")
    print("Next: python manage.py test bookings.test_dashboard_ui_v135 bookings.test_mobile_v133 --settings=config.settings")


if __name__ == "__main__":
    main()
