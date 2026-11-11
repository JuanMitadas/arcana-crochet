# One image for development (docker compose) and production (AWS Lambda).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Lambda Web Adapter: on Lambda it turns each event into an HTTP request to gunicorn
# on port 8000. Outside Lambda (docker compose) it stays idle.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.0.1 /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_PORT=8000 \
    AWS_LWA_READINESS_CHECK_PATH=/healthz/ \
    AWS_LWA_READINESS_CHECK_HEALTHY_STATUS=200-399 \
    AWS_LWA_PASS_THROUGH_PATH=/healthz/

WORKDIR /app

COPY requirements/ requirements/
ARG REQUIREMENTS=base
RUN pip install -r requirements/${REQUIREMENTS}.txt

COPY . .

# collectstatic runs at build time (the Lambda disk is read-only); these variables only
# exist so the command can run. Precompiled bytecode shortens the cold start.
RUN SECRET_KEY=build DATABASE_URL=sqlite:////tmp/build.db python manage.py collectstatic --noinput \
    && python -m compileall -q -j 0 apps config

RUN useradd --create-home --uid 1000 arcana \
    && mkdir -p /app/media \
    && chown -R arcana:arcana /app/media
USER arcana

EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
# One worker per instance: Lambda delivers one request at a time. On another server,
# set WEB_CONCURRENCY for more workers. No control socket (read-only disk).
# --timeout 0: Lambda freezes the instance between requests, and gunicorn's worker
# timeout counted that frozen time, killed the worker on the next request and started
# a new one, which loads Django again (~3 s). Lambda's own 30 s timeout still applies.
# --preload: Django loads once in the master, so a replacement worker starts at once.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "0", "--preload", "--no-control-socket", "--access-logfile", "-"]
