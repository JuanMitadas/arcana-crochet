"""No-op: already part of 0001_initial (see config/migracoes/__init__.py)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("account", "0003_alter_emailaddress_create_unique_verified_email")]
    operations = []
