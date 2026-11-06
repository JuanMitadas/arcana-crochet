#!/usr/bin/env bash
# Creates or updates the store's secrets in SSM Parameter Store (/arcana/<environment>/).
#
# Run it in AWS CloudShell (it ships with the AWS CLI), in the sa-east-1 region:
#   bash infra/configurar-segredos.sh            # prod environment
#
# SECRET_KEY and ORIGEM_SEGREDO are generated the first time and kept afterwards. The
# other values are asked for; leave one blank to keep it as it is. The database needs
# no secret: the Lambda connects to Aurora DSQL with an IAM token.
set -euo pipefail

ambiente="${1:-prod}"
prefixo="/arcana/${ambiente}"
regiao="${AWS_REGION:-sa-east-1}"

existe() {
  aws ssm get-parameter --region "$regiao" --name "$prefixo/$1" >/dev/null 2>&1
}

gravar() { # name value type
  aws ssm put-parameter --region "$regiao" --name "$prefixo/$1" --value "$2" \
    --type "$3" --overwrite >/dev/null
  echo "  ✓ $prefixo/$1"
}

gerar() {
  python3 -c "import secrets; print(secrets.token_urlsafe(50))"
}

perguntar() { # name description type
  local valor
  read -r -s -p "$2 (Enter to skip): " valor
  echo
  if [[ -n "$valor" ]]; then
    gravar "$1" "$valor" "$3"
  fi
}

echo "Secrets in $prefixo (region $regiao)"

existe SECRET_KEY || gravar SECRET_KEY "$(gerar)" SecureString
# String (not SecureString) because CloudFormation has to read the value to set the
# X-Arcana-Origem header on CloudFront.
existe ORIGEM_SEGREDO || gravar ORIGEM_SEGREDO "$(gerar)" String

perguntar EMAIL_URL "SMTP for emails, e.g. smtp+tls://resend:<api-key>@smtp.resend.com:587" SecureString
perguntar DEFAULT_FROM_EMAIL "Sender, e.g. Arcana Crochet <nao-responda@arcanacrochet.com.br>" String
perguntar ADMIN_URL "Admin path, e.g. painel-x7k2/ (end it with /)" String

echo "Done. Current parameters:"
aws ssm get-parameters-by-path --region "$regiao" --path "$prefixo" \
  --query "Parameters[].Name" --output text | tr '\t' '\n'
