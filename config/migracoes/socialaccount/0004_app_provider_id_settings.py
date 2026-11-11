"""No-op: already part of 0001_initial (see config/migracoes/__init__.py)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("socialaccount", "0003_extra_data_default_dict")]
    operations = []
