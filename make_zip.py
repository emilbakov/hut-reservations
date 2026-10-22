
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parent / "summitdesk_v126.zip"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "staticfiles",
    "media",
    ".pytest_cache",
    ".idea",
    ".vscode",
}

EXCLUDE_FILES = {
    ".env",
    "db.sqlite3",
    "local_settings.py",
    "make_zip.py",
}

EXCLUDE_EXTENSIONS = {
    ".pyc", ".sqlite3", ".log",
    ".pem", ".key", ".p12",
}

with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as zip_file:
    for file in ROOT.rglob("*"):
        if not file.is_file():
            continue

        relative = file.relative_to(ROOT)

        if any(part in EXCLUDE_DIRS for part in relative.parts):
            continue

        if file.name in EXCLUDE_FILES:
            continue

        if file.name.startswith(".env"):
            continue

        if file.suffix in EXCLUDE_EXTENSIONS:
            continue

        zip_file.write(file, relative)

print(f"ZIP created: {OUTPUT}")
print(f"Size: {OUTPUT.stat().st_size / 1024 / 1024:.2f} MB")
