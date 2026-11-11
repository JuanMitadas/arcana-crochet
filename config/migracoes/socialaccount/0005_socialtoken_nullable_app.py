"""No-op: already part of 0001_initial (see config/migracoes/__init__.py)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("socialaccount", "0004_app_provider_id_settings")]
    operations = []
