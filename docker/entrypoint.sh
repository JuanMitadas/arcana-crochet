#!/bin/sh
set -e

# Só o container web aplica as migrações (RUN_MIGRATIONS=1), para não haver corrida
# entre web, worker e beat subindo ao mesmo tempo.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
