"""No-op: already part of 0001_initial (see config/migracoes/__init__.py)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("mfa", "0002_authenticator_timestamps")]
    operations = []
