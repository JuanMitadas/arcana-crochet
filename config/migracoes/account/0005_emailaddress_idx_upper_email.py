"""No-op: already part of 0001_initial (see config/migracoes/__init__.py)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("account", "0004_alter_emailaddress_drop_unique_email")]
    operations = []
