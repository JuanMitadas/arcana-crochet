# Imagem única usada pelo web, pelo worker e pelo beat.
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
ARG REQUIREMENTS=base
RUN pip install -r requirements/${REQUIREMENTS}.txt

COPY . .

# collectstatic roda no build; estas variáveis só existem para o comando funcionar.
RUN SECRET_KEY=build DATABASE_URL=sqlite:////tmp/build.db python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 arcana \
    && mkdir -p /app/media \
    && chown -R arcana:arcana /app/media
USER arcana

EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "30", "--access-logfile", "-"]
