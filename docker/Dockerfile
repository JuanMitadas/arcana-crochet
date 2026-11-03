# Imagem única: desenvolvimento (docker compose) e produção (AWS Lambda).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Lambda Web Adapter: na Lambda, transforma cada evento em um pedido HTTP para o
# gunicorn na porta 8000. Fora da Lambda (docker compose) ele fica inativo.
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

# collectstatic roda no build (o disco da Lambda é somente leitura); estas variáveis
# só existem para o comando funcionar. O bytecode pré-compilado encurta o cold start.
RUN SECRET_KEY=build DATABASE_URL=sqlite:////tmp/build.db python manage.py collectstatic --noinput \
    && python -m compileall -q -j 0 apps config

RUN useradd --create-home --uid 1000 arcana \
    && mkdir -p /app/media \
    && chown -R arcana:arcana /app/media
USER arcana

EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
# Um worker por instância: a Lambda entrega um pedido de cada vez. Em outro servidor,
# defina WEB_CONCURRENCY para mais workers. Sem socket de controle (disco só leitura).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "29", "--no-control-socket", "--access-logfile", "-"]
