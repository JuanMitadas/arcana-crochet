#!/usr/bin/env bash
# Cria ou atualiza os segredos da loja no SSM Parameter Store (/arcana/<ambiente>/).
#
# Rode no AWS CloudShell (já vem com a AWS CLI), na região sa-east-1:
#   bash infra/configurar-segredos.sh            # ambiente prod
#
# SECRET_KEY e ORIGEM_SEGREDO são gerados automaticamente na primeira vez e mantidos
# depois. Os demais valores são perguntados; deixe em branco para não mexer.
set -euo pipefail

ambiente="${1:-prod}"
prefixo="/arcana/${ambiente}"
regiao="${AWS_REGION:-sa-east-1}"

existe() {
  aws ssm get-parameter --region "$regiao" --name "$prefixo/$1" >/dev/null 2>&1
}

gravar() { # nome valor tipo
  aws ssm put-parameter --region "$regiao" --name "$prefixo/$1" --value "$2" \
    --type "$3" --overwrite >/dev/null
  echo "  ✓ $prefixo/$1"
}

gerar() {
  python3 -c "import secrets; print(secrets.token_urlsafe(50))"
}

perguntar() { # nome descricao tipo
  local valor
  read -r -s -p "$2 (Enter para pular): " valor
  echo
  if [[ -n "$valor" ]]; then
    gravar "$1" "$valor" "$3"
  fi
}

echo "Segredos em $prefixo (região $regiao)"

existe SECRET_KEY || gravar SECRET_KEY "$(gerar)" SecureString
# String (não SecureString) porque o CloudFormation precisa ler o valor para
# configurar o cabeçalho X-Arcana-Origem no CloudFront.
existe ORIGEM_SEGREDO || gravar ORIGEM_SEGREDO "$(gerar)" String

perguntar DATABASE_URL "Connection string POOLED do Neon (postgresql://...-pooler...)" SecureString
perguntar EMAIL_URL "SMTP para os e-mails, ex.: smtp+tls://resend:<api-key>@smtp.resend.com:587" SecureString
perguntar DEFAULT_FROM_EMAIL "Remetente, ex.: Arcana Crochet <nao-responda@arcanacrochet.com.br>" String
perguntar ADMIN_URL "Caminho do painel, ex.: painel-x7k2/ (termine com /)" String

echo "Pronto. Parâmetros atuais:"
aws ssm get-parameters-by-path --region "$regiao" --path "$prefixo" \
  --query "Parameters[].Name" --output text | tr '\t' '\n'
