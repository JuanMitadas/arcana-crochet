"""No-op: already part of 0001_initial (see config/migracoes/__init__.py)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("auth", "0011_update_proxy_permissions")]
    operations = []
