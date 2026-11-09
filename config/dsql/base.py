"""Aurora DSQL database engine: the official adapter plus fixes this project needs.

``ENGINE = "config.dsql"`` in settings. The adapter creates plain unique indexes with
``CREATE UNIQUE INDEX ASYNC`` but leaves conditional ones (``UniqueConstraint`` with
``condition=``, used by django-allauth) on PostgreSQL's synchronous syntax, which DSQL
rejects.
"""

from aurora_dsql_django import base, schema


class DatabaseSchemaEditor(schema.DatabaseSchemaEditor):
    sql_create_unique_index = (
        "CREATE UNIQUE INDEX ASYNC %(name)s ON %(table)s (%(columns)s)%(include)s%(condition)s"
    )


class DatabaseWrapper(base.DatabaseWrapper):
    SchemaEditorClass = DatabaseSchemaEditor
