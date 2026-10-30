#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/deploy/hut-reservations"
ENV_FILE="/etc/hut-reservations/postgres.env"

cd "$PROJECT_DIR"

echo "Checking production PostgreSQL migrations..."

set -a
source "$ENV_FILE"
set +a

export DJANGO_SETTINGS_MODULE=config.settings_postgres

myprojectenv/bin/python manage.py migrate --check --noinput

echo "All production database migrations are applied."
