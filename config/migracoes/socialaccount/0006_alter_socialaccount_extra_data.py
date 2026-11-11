"""No-op: already part of 0001_initial (see config/migracoes/__init__.py)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("socialaccount", "0005_socialtoken_nullable_app")]
    operations = []
