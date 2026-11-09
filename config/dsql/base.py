"""Aurora DSQL database engine: the official adapter plus fixes this project needs.

``ENGINE = "config.dsql"`` in settings.

- The adapter creates plain unique indexes with ``CREATE UNIQUE INDEX ASYNC`` but leaves
  conditional ones (``UniqueConstraint`` with ``condition=``, used by django-allauth)
  on PostgreSQL's synchronous syntax, which DSQL rejects.
- Right after a schema change, DSQL may refuse the next DDL statement with
  "schema has been updated by another transaction (OC001)" while the change spreads
  through the cluster. Migrations run each statement in its own transaction, so a
  statement that failed this way can simply be sent again.
"""

import time

from aurora_dsql_django import base, schema
from django.db import OperationalError

from apps.core.transacoes import conflito_occ

TENTATIVAS_DDL = 6


class DatabaseSchemaEditor(schema.DatabaseSchemaEditor):
    sql_create_unique_index = (
        "CREATE UNIQUE INDEX ASYNC %(name)s ON %(table)s (%(columns)s)%(include)s%(condition)s"
    )

    def execute(self, sql, params=()):
        for tentativa in range(1, TENTATIVAS_DDL + 1):
            try:
                return super().execute(sql, params)
            except OperationalError as erro:
                # Inside a transaction the whole transaction has to start over, which
                # is the caller's job (see apps.core.transacoes.atomico).
                if (
                    tentativa == TENTATIVAS_DDL
                    or self.connection.in_atomic_block
                    or not conflito_occ(erro)
                ):
                    raise
                time.sleep(0.5 * tentativa)


class DatabaseWrapper(base.DatabaseWrapper):
    SchemaEditorClass = DatabaseSchemaEditor
