# Deploy na AWS (Lambda + CloudFront) com banco no Neon

A loja roda numa função **Lambda** em São Paulo, atrás do **CloudFront**. As fotos ficam no **S3** e o banco é um Postgres serverless gratuito no **Neon**, também em São Paulo. Com pouco movimento, o custo fica em torno de **US$ 1 por mês**: o domínio no Route 53 (US$ 0,50) e centavos de S3 e ECR.

```
visitante → CloudFront ─┬─ /media/*  → S3 (fotos)
                        ├─ /static/* → Lambda (cache de 1 ano na borda)
                        └─ resto     → Lambda (Django) → Neon (Postgres)
```

| Peça | Onde está | Arquivo |
| --- | --- | --- |
| Infra da loja (Lambda, CloudFront, S3, aquecimento) | pilha `arcana-prod` | `infra/template.yaml` |
| Repositório de imagens e papel do GitHub | pilha `arcana-base` (criada uma vez) | `infra/base.yaml` |
| Segredos | SSM Parameter Store, em `/arcana/prod/` | `infra/configurar-segredos.sh` |
| Deploy a cada push na `main` | GitHub Actions | `.github/workflows/deploy.yml` |
| Backup diário do banco | GitHub Actions → S3 | `.github/workflows/backup.yml` |

Faça os passos 1 a 6 uma vez. Depois disso, publicar é só fazer merge na `main`.

## 1. Conta AWS

1. Crie a conta em https://aws.amazon.com com seu e-mail pessoal.
   - No cadastro, a AWS pergunta entre **Free plan** e **Paid plan**. As duas dão os créditos de conta nova. Confira na tela o que acontece com a "Free plan" ao fim dos 6 meses; se ela for encerrada sem migração, escolha "Paid plan". Os serviços desta loja ficam na cota grátis permanente de qualquer jeito.
2. **Proteja a conta raiz:** ative o MFA (menu da conta → Security credentials). Depois disso, use a conta raiz só para cobrança.
3. **Crie seu usuário do dia a dia:** abra o **IAM Identity Center**, ative, crie um usuário para você e dê a ele o conjunto de permissões `AdministratorAccess`. Entre no console por esse usuário daqui em diante.
4. **Alerta de gasto:** Billing and Cost Management → **Budgets** → Create budget → *Monthly cost budget*, valor **US$ 1**, alerta por e-mail. Se algo sair do previsto, você fica sabendo no mesmo dia.
5. Deixe o console na região **South America (São Paulo) sa-east-1** (canto superior direito).

## 2. Banco no Neon

1. Crie a conta em https://neon.com e um projeto chamado `arcana`:
   - **Region:** AWS South America East 1 (São Paulo)
   - **Postgres:** a versão mais recente oferecida
2. Em **Connect**, copie duas connection strings do banco `neondb`:
   - **Pooled** (o host tem `-pooler`): usada pelo site, que abre muitas conexões curtas.
   - **Direta** (desligue "Connection pooling"): usada pelas migrações e pelo backup.

O plano grátis tem 1 GB de banco e 100 CU-horas de processamento por mês, e o banco "dorme" depois de 5 minutos parado. A primeira visita depois disso demora cerca de meio segundo a mais.

## 3. Base na AWS (uma vez)

Abra o **CloudShell** (ícone `>_` no topo do console). Ele já vem com a AWS CLI e com permissão do seu usuário.

```bash
git clone https://github.com/JuanMitadas/arcana-crochet.git
cd arcana-crochet
aws cloudformation deploy --region sa-east-1 \
  --stack-name arcana-base \
  --template-file infra/base.yaml \
  --capabilities CAPABILITY_NAMED_IAM
aws cloudformation describe-stacks --region sa-east-1 --stack-name arcana-base \
  --query "Stacks[0].Outputs" --output table
```

Anote o **PapelDeployArn**. Se aparecer erro dizendo que o provedor `token.actions.githubusercontent.com` já existe, rode de novo acrescentando `--parameter-overrides CriarProvedorOidc=false`.

O papel criado só pode ser assumido por workflows do repositório `JuanMitadas/arcana-crochet` rodando no environment `producao` do GitHub. Nenhuma chave da AWS fica guardada no GitHub.

## 4. Segredos

Ainda no CloudShell, na pasta do projeto:

```bash
bash infra/configurar-segredos.sh
```

O script gera sozinho a `SECRET_KEY` e o segredo que o CloudFront envia à Lambda (`ORIGEM_SEGREDO`). Depois pergunta:

- **DATABASE_URL:** a connection string **pooled** do Neon.
- **EMAIL_URL:** o SMTP para os e-mails ([contas-externas.md](contas-externas.md#5-e-mail-transacional)). **Sem ele, ninguém consegue criar conta** na loja publicada, porque o cadastro exige confirmar o e-mail. Pode pular agora e rodar o script de novo depois.
- **DEFAULT_FROM_EMAIL** e **ADMIN_URL** (caminho do painel; use algo difícil de adivinhar, como `painel-x7k2/`).

Rodar o script de novo só altera o que você digitar. Para trocar um valor depois, rode o script outra vez. A Lambda lê os segredos quando sobe, então a mudança vale a partir do próximo deploy.

## 5. GitHub

No repositório: **Settings → Environments → New environment** → `producao`.

1. **Deployment branches and tags:** *Selected branches and tags* → adicione `main`.
2. **Environment secrets:**
   - `AWS_ROLE_ARN`: o PapelDeployArn do passo 3
   - `DATABASE_URL_DIRETA`: a connection string **direta** do Neon
3. **Environment variables** (deixe sem criar enquanto não tiver domínio próprio):
   - `DOMINIO`: ex. `arcanacrochet.com.br`
   - `CERTIFICADO_ARN`: ARN do certificado do passo 7

Não marque "Required reviewers" nesse environment, senão o backup diário fica parado esperando aprovação.

## 6. Primeiro deploy

Abra um pull request de `dev` para `main` e faça o merge. O workflow **Deploy na AWS** roda sozinho e faz quatro coisas:

1. monta a imagem da Lambda (Dockerfile com o Lambda Web Adapter);
2. aplica as migrações no Neon pela conexão direta;
3. publica com o AWS SAM;
4. confere `/healthz/?banco=1`.

O primeiro deploy leva cerca de 10 minutos, porque o CloudFront demora para se espalhar pelas bordas. O endereço da loja aparece no resumo do workflow (`https://dxxxx.cloudfront.net`). Também dá para rodar à mão em **Actions → Deploy na AWS → Run workflow**.

**Criar o seu usuário administrador.** No seu computador, na pasta do projeto, use a conexão direta:

```bash
DATABASE_URL='<connection string direta>' SECRET_KEY=temporaria python manage.py createsuperuser
```

**Peças de exemplo no site publicado (opcional, para o portfólio).** Isso cria as peças de demonstração direto no Neon e as fotos no S3. Precisa da AWS CLI configurada no seu computador com o seu usuário (`aws configure sso`):

```bash
DEBUG=1 DATABASE_URL='<direta>' SECRET_KEY=temporaria MIDIA_BUCKET='<BucketMidia da pilha arcana-prod>' \
  AWS_REGION=sa-east-1 python manage.py popular_demo
```

O `DEBUG=1` vale só para esse comando no seu computador; o site continua em produção. Antes de vender de verdade, rode o mesmo comando com `--limpar` para apagar a cliente de teste e as peças de exemplo.

## 7. Domínio próprio (opcional)

O certificado do CloudFront precisa estar na região **us-east-1**, e o domínio raiz (sem www) só aponta para o CloudFront com um registro *alias*. Por isso o DNS fica no Route 53, que custa US$ 0,50 por mês.

1. **Route 53 → Hosted zones → Create hosted zone** com o seu domínio. Copie os 4 servidores **NS** e coloque-os no Registro.br (seu domínio → DNS → *Alterar servidores DNS*). A troca leva de minutos a algumas horas.
2. Troque a região do console para **N. Virginia (us-east-1)** e abra **Certificate Manager → Request certificate**. Peça o certificado para `seudominio.com.br` e `www.seudominio.com.br`, com validação por **DNS**. Clique em **Create records in Route 53** e espere o status ficar *Issued*.
3. No GitHub, crie as variáveis `DOMINIO` e `CERTIFICADO_ARN` no environment `producao` e rode o deploy de novo.
4. Volte ao Route 53, na zona do domínio, e crie quatro registros: **A** e **AAAA** para o domínio raiz e para o `www`, todos com *Alias* apontando para a distribuição do CloudFront.

Acessos pelo `www` são redirecionados para o domínio sem www pela própria borda do CloudFront.

## 8. Backup e restauração

- **Todo dia às 3h30** o workflow **Backup do banco** exporta o Neon e guarda o arquivo no bucket de backups. O bucket apaga sozinho os arquivos com mais de 30 dias. Rode uma vez à mão (**Actions → Backup do banco → Run workflow**) para conferir.
- **O Neon também guarda as últimas 6 horas** e restaura para qualquer momento desse intervalo (Neon → Branches → Restore). Para erros recentes, é o caminho mais rápido.
- **As fotos** ficam no S3 com versionamento: uma foto apagada ou trocada pode ser recuperada por 30 dias (S3 → bucket → *Show versions*).

**Restaurar um backup diário.** Faça primeiro numa *branch* do Neon, para conferir sem mexer no site:

1. Baixe o arquivo: S3 → bucket de backups → escolha o `.dump` → Download.
2. No Neon, crie uma branch vazia (Branches → Create branch) e copie a connection string direta dela.
3. Restaure:
   ```bash
   docker run --rm -i postgres:18 pg_restore --no-owner --no-privileges -d '<connection string da branch>' < banco-AAAA-MM-DDTHHMMZ.dump
   ```
4. Se estiver tudo certo, promova a branch a principal no Neon (Branches → *Set as default*) ou restaure o arquivo na branch principal.

**Ensaie isso uma vez por mês.** Backup que nunca foi restaurado não é backup.

## 9. Acompanhar e atualizar

- **Publicar:** merge na `main`. Para voltar atrás, reverta o commit (`git revert`) e faça merge de novo.
- **Logs:** CloudWatch → Log groups → `/aws/lambda/arcana-prod-site` (guardados por 14 dias).
- **Site no ar:** cadastre `https://seudominio/healthz/?banco=1` no UptimeRobot, com intervalo de **30 minutos**. Intervalos menores mantêm o Neon acordado e gastam a cota grátis de processamento.
- **Custos:** Billing → *Bills* mostra o mês corrente por serviço, e o alerta de US$ 1 avisa se algo fugir do previsto.

## 10. Limites desta arquitetura

- **Primeira visita mais lenta.** Depois de um tempo parado, o primeiro acesso soma o cold start da Lambda (1 a 3 s) e o despertar do Neon (cerca de 0,5 s). Um agendamento do EventBridge chama a Lambda a cada 5 minutos para mantê-la aquecida, de graça e sem acordar o banco.
- **Uploads de até 6 MB por pedido** (limite da URL da Lambda). Reduza as fotos antes de enviar pelo painel. Vídeos de produto maiores que isso precisarão de upload direto para o S3, que fica para uma fase futura.
- **Neon grátis:** 1 GB de banco, 100 CU-horas e 5 GB de tráfego por mês. Quando a loja crescer, o plano pago do Neon ou um RDS resolvem sem mudar o código, só a `DATABASE_URL`.

## Desmontar

```bash
aws cloudformation delete-stack --region sa-east-1 --stack-name arcana-prod
```

Os buckets de fotos e de backups são mantidos de propósito (`DeletionPolicy: Retain`). Apague-os à mão no S3 se quiser mesmo remover tudo.
