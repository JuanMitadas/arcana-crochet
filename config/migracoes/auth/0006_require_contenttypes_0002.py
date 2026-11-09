"""No-op: already part of 0001_initial (see config/migracoes/__init__.py)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("auth", "0005_alter_user_last_login_null")]
    operations = []
