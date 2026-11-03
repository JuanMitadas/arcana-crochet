"""Carrega segredos do AWS SSM Parameter Store para o ambiente.

Na Lambda, a variável AWS_SSM_PREFIX (ex.: /arcana/prod/) aponta para uma pasta de
parâmetros. Cada parâmetro vira uma variável de ambiente com o nome do último
trecho do caminho: /arcana/prod/SECRET_KEY → SECRET_KEY.

Variáveis já definidas no ambiente têm prioridade, e o carregamento acontece uma
vez por instância (no cold start), antes de o settings ler as variáveis.
"""

import os


def carregar_parametros(prefixo: str, cliente=None) -> list[str]:
    """Copia os parâmetros do prefixo para os.environ. Devolve os nomes carregados."""
    if not prefixo:
        return []
    if cliente is None:
        import boto3  # importado só na Lambda: não pesa no desenvolvimento

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
