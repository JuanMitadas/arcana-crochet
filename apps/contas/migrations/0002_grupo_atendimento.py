"""Cria o grupo "Atendimento" com as permissões do papel de atendente.

Para dar acesso a alguém da equipe: papel "Atendente" + grupo "Atendimento".
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

PERMISSOES = [
    ("catalogo", "view_categoria"),
    ("catalogo", "view_produto"),
    ("catalogo", "view_produtovariacao"),
    ("catalogo", "view_produtofoto"),
    ("catalogo", "view_movimentacaoestoque"),
    ("catalogo", "add_movimentacaoestoque"),
    ("contas", "view_usuario"),
]


def criar_grupo(apps, schema_editor):
    for config in apps.get_app_configs():
        config.models_module = True
        create_permissions(config, apps=apps, verbosity=0)
        config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    grupo, _ = Group.objects.get_or_create(name="Atendimento")
    for app_label, codename in PERMISSOES:
        grupo.permissions.add(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )


def remover_grupo(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name="Atendimento").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("contas", "0001_initial"),
        ("catalogo", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(criar_grupo, remover_grupo)]
