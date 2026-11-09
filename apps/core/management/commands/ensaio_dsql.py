"""Rehearse the migrations as Aurora DSQL would run them, on a plain PostgreSQL.

With the DSQL engine configured but pointing at a scratch PostgreSQL (see the CI
workflow), this applies every migration through the DSQL adapter and writes each schema
statement (DDL) it sends to stdout. Piping that to ``dsql-lint`` catches migrations DSQL
can't run before they reach production::

    python manage.py ensaio_dsql | dsql-lint -

PostgreSQL doesn't know DSQL's asynchronous DDL, so those statements are rewritten to
their synchronous form before running; the output keeps the original DSQL text.
"""

import re

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections

DML = re.compile(r"^(SELECT|INSERT|UPDATE|DELETE|SAVEPOINT|RELEASE|ROLLBACK)\b", re.I)
ASYNC = re.compile(r"^(CREATE (?:UNIQUE )?INDEX|ALTER TABLE) ASYNC ", re.IGNORECASE)


class Command(BaseCommand):
    help = "Apply all migrations through the DSQL adapter and print the SQL sent."

    def handle(self, *args, **options):
        connection = connections[DEFAULT_DB_ALIAS]
        if connection.vendor != "dsql":
            raise CommandError("Configure DSQL_ENDPOINT so the DSQL engine is used.")

        def executar(execute, sql, params, many, context):
            texto = str(sql).strip()
            if not DML.match(texto):
                self.stdout.write(texto.rstrip(";") + ";")
            if texto.upper().startswith("CALL SYS.WAIT_FOR_JOB"):
                return execute("SELECT true", None, many, context)
            postgres = ASYNC.sub(r"\1 ", texto)
            if postgres != texto and "VALIDATE CONSTRAINT" in postgres.upper():
                # DSQL answers with a job id that the adapter then waits for.
                execute(postgres, params, many, context)
                return execute("SELECT 'ensaio'", None, many, context)
            return execute(postgres, params, many, context)

        with connection.execute_wrapper(executar):
            call_command("migrate", interactive=False, verbosity=0)
