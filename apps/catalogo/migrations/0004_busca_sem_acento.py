from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    """Busca que ignora acentos ("croche" encontra "crochê") e tolera erros de digitação."""

    dependencies = [("catalogo", "0003_vitrine")]

    operations = [UnaccentExtension(), TrigramExtension()]
