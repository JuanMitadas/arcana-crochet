#!/bin/sh
set -e

# No docker compose de desenvolvimento, aplica as migrações ao subir (RUN_MIGRATIONS=1).
# Na AWS as migrações rodam no deploy (GitHub Actions), não a cada cold start.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
