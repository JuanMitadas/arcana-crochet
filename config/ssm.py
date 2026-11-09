"""Load secrets from AWS SSM Parameter Store into the environment.

On Lambda, AWS_SSM_PREFIX (e.g. /arcana/prod/) points to a folder of parameters.
Each parameter becomes an environment variable named after the last part of its
path: /arcana/prod/SECRET_KEY → SECRET_KEY.

Variables already set in the environment win, and loading happens once per instance
(at cold start), before the settings read the variables.
"""

import os


def carregar_parametros(prefixo: str, cliente=None) -> list[str]:
    """Copy the prefix's parameters into os.environ. Return the names loaded."""
    if not prefixo:
        return []
    if cliente is None:
        import boto3  # imported only on Lambda: no cost in development

        cliente = boto3.client("ssm")
    prefixo = "/" + prefixo.strip("/") + "/"
    carregados = []
    for pagina in cliente.get_paginator("get_parameters_by_path").paginate(
        Path=prefixo, Recursive=False, WithDecryption=True
    ):
        for parametro in pagina["Parameters"]:
            nome = parametro["Name"].rsplit("/", 1)[-1]
            if nome not in os.environ:
                os.environ[nome] = parametro["Value"]
                carregados.append(nome)
    return carregados
