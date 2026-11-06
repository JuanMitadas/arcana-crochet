#!/bin/sh
set -e

# In the development docker compose, apply migrations on start (RUN_MIGRATIONS=1).
# On AWS, migrations run during the deploy (GitHub Actions), not on every cold start.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
