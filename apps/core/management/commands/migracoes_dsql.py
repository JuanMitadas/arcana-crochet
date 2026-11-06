"""Rebuild config/migracoes/: Django and allauth migrations as one final-state 0001.

Run after upgrading Django or django-allauth when tests/test_dsql.py fails::

    python manage.py migracoes_dsql

Databases that are already migrated are not affected: the migration names stay the
same, and the new 0001 describes the schema they already have.
"""

import importlib
import pkgutil
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.graph import MigrationGraph
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState
from django.db.migrations.writer import MigrationWriter
from django.utils import translation

CABECALHO = (
    "# Final schema of this app's migrations, rebuilt for Aurora DSQL"
    " (see config/migracoes/__init__.py).\n"
)
STUB = '''"""No-op: already part of 0001_initial (see config/migracoes/__init__.py)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("{app}", "{anterior}")]
    operations = []
'''


def migracoes_originais(app_label: str) -> list[str]:
    """Names of the migrations shipped with the app, ignoring MIGRATION_MODULES."""
    pacote = importlib.import_module(apps.get_app_config(app_label).name + ".migrations")
    return sorted(nome for _, nome, _ in pkgutil.iter_modules(pacote.__path__))


class Command(BaseCommand):
    help = "Rebuild the final-state migrations in config/migracoes/."

    def handle(self, *args, **options):
        alvos = list(settings.MIGRATION_MODULES)
        pastas = {
            app: Path(settings.BASE_DIR, *modulo.split("."))
            for app, modulo in settings.MIGRATION_MODULES.items()
        }
        for pasta in pastas.values():
            # The autodetector only proposes an initial migration for empty packages.
            for arquivo in pasta.glob("0*.py"):
                arquivo.unlink()

        # Strings in the migrations stay in English, as in the original files.
        with translation.override("en"):
            mudancas = MigrationAutodetector(
                ProjectState(),
                ProjectState.from_apps(apps),
                NonInteractiveMigrationQuestioner(),
            ).changes(graph=MigrationGraph(), trim_to_apps=set(alvos))

            for app in alvos:
                (migracao,) = mudancas[app]
                texto = MigrationWriter(migracao).as_string()
                texto = CABECALHO + texto.split("\n", 1)[1]
                (pastas[app] / "0001_initial.py").write_text(texto)
                anterior = "0001_initial"
                originais = migracoes_originais(app)
                for nome in originais[1:]:
                    (pastas[app] / f"{nome}.py").write_text(STUB.format(app=app, anterior=anterior))
                    anterior = nome
                self.stdout.write(f"{app}: 0001_initial + {len(originais) - 1} empty files")
