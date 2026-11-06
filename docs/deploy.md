# Deploying to AWS (Lambda + CloudFront + Aurora DSQL)

The store runs on a **Lambda** function in São Paulo, behind **CloudFront**. Photos live on **S3** and the database is **Aurora DSQL**, a serverless PostgreSQL-compatible database, also in São Paulo. With little traffic the cost stays around **US$ 1 a month**: the Route 53 hosted zone (US$ 0.50) plus cents of S3, ECR and backups. See [architecture.md](architecture.md) for the diagram and the full list of services.

```
visitor → CloudFront ─┬─ /media/*  → S3 (photos)
                      ├─ /static/* → Lambda (cached for a year at the edge)
                      └─ rest      → Lambda (Django) → Aurora DSQL
```

| Piece | Where it lives | File |
| --- | --- | --- |
| Store infrastructure (Lambda, CloudFront, S3, database, backups, warm-up) | stack `arcana-prod` | `infra/template.yaml` |
| Image repository and GitHub role | stack `arcana-base` (created once) | `infra/base.yaml` |
| Secrets | SSM Parameter Store, under `/arcana/prod/` | `infra/configurar-segredos.sh` |
| Deploy on every push to `main` | GitHub Actions | `.github/workflows/deploy.yml` |
| Daily database backup | AWS Backup (part of the stack) | `infra/template.yaml` |

Do steps 1 to 5 once. After that, publishing is just merging into `main`.

## 1. AWS account

1. Create the account at https://aws.amazon.com with your personal email.
   - At sign-up AWS asks for the **Free plan** or the **Paid plan**. Both come with the new-account credits. Check on screen what happens to the Free plan after its 6 months; if it gets closed without migrating, pick the Paid plan. The services used here stay within the always-free tiers either way.
2. **Protect the root user:** turn on MFA (account menu → Security credentials). From then on, use the root user for billing only.
3. **Create your everyday user:** open **IAM Identity Center**, enable it, create a user for yourself and give it the `AdministratorAccess` permission set. Sign in to the console with that user from now on.
4. **Spending alert:** Billing and Cost Management → **Budgets** → Create budget → *Monthly cost budget*, amount **US$ 1**, email alert. If anything goes off plan, you hear about it the same day.
5. Keep the console in the **South America (São Paulo) sa-east-1** region (top right corner).

## 2. Base stack (once)

Open **CloudShell** (the `>_` icon at the top of the console). It comes with the AWS CLI and your user's permissions.

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

Write down **PapelDeployArn**. If you get an error saying the `token.actions.githubusercontent.com` provider already exists, run it again adding `--parameter-overrides CriarProvedorOidc=false`.

The role can only be assumed by workflows of the `JuanMitadas/arcana-crochet` repository running in the GitHub `producao` environment. No AWS key is stored on GitHub.

## 3. Secrets

Still in CloudShell, in the project folder:

```bash
bash infra/configurar-segredos.sh
```

The script generates the `SECRET_KEY` and the secret CloudFront sends to the Lambda (`ORIGEM_SEGREDO`) by itself. Then it asks for:

- **EMAIL_URL:** the SMTP server for emails ([external-accounts.md](external-accounts.md#5-transactional-email)). **Without it nobody can sign up** on the published store, because sign-up requires confirming the email. You can skip it now and run the script again later.
- **DEFAULT_FROM_EMAIL** and **ADMIN_URL** (the admin path; use something hard to guess, like `painel-x7k2/`).

There is no database password to store: the Lambda connects to Aurora DSQL with an IAM token signed by its own role.

Running the script again only changes what you type. The Lambda reads the secrets when it starts, so a change takes effect from the next deploy.

## 4. GitHub

In the repository: **Settings → Environments → New environment** → `producao`.

1. **Deployment branches and tags:** *Selected branches and tags* → add `main`.
2. **Environment secret** `AWS_ROLE_ARN`: the PapelDeployArn from step 2.
3. **Environment variables** (leave them out until you have a custom domain):
   - `DOMINIO`: e.g. `arcanacrochet.com.br`
   - `CERTIFICADO_ARN`: ARN of the certificate from step 6

## 5. First deploy

Open a pull request from `dev` to `main` and merge it. The **Deploy to AWS** workflow runs by itself and:

1. builds the Lambda image (Dockerfile with the Lambda Web Adapter);
2. publishes with AWS SAM, which on the first run also creates the Aurora DSQL cluster;
3. applies the migrations on Aurora DSQL (on later deploys this happens *before* publishing, so the new code never runs against an old schema);
4. checks `/healthz/?banco=1`.

The first deploy takes about 10 minutes, because CloudFront takes a while to spread to the edge locations. The store address shows up in the workflow summary (`https://dxxxx.cloudfront.net`). You can also run it by hand in **Actions → Deploy to AWS → Run workflow**.

**Commands against the production database** run on your computer, with your AWS user. Install the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html), sign in once with `aws configure sso` (IAM Identity Center, region sa-east-1) and take the endpoint from the stack outputs (`BancoEndpoint`):

```bash
aws cloudformation describe-stacks --region sa-east-1 --stack-name arcana-prod \
  --query "Stacks[0].Outputs[?OutputKey=='BancoEndpoint'].OutputValue" --output text
```

**Create your admin user:**

```bash
DSQL_ENDPOINT='<BancoEndpoint>' AWS_PROFILE='<your SSO profile>' SECRET_KEY=temporary \
  python manage.py createsuperuser
```

**Demo pieces on the published site (optional, for the portfolio).** This creates the demo pieces in Aurora DSQL and their photos on S3:

```bash
DEBUG=1 DSQL_ENDPOINT='<BancoEndpoint>' AWS_PROFILE='<your SSO profile>' SECRET_KEY=temporary \
  MIDIA_BUCKET='<BucketMidia from the arcana-prod stack>' AWS_REGION=sa-east-1 \
  python manage.py popular_demo
```

`DEBUG=1` only applies to that command on your computer; the site stays in production mode. Before selling for real, run the same command with `--limpar` to delete the test customer and the demo pieces.

## 6. Custom domain (optional)

The CloudFront certificate must be in the **us-east-1** region, and the apex domain (without www) can only point to CloudFront with an *alias* record. That's why DNS lives in Route 53, which costs US$ 0.50 a month.

1. **Route 53 → Hosted zones → Create hosted zone** with your domain. Copy the 4 **NS** servers into Registro.br (your domain → DNS → *Alterar servidores DNS*). The switch takes from minutes to a few hours.
2. Switch the console region to **N. Virginia (us-east-1)** and open **Certificate Manager → Request certificate**. Request it for `yourdomain.com.br` and `www.yourdomain.com.br`, with **DNS** validation. Click **Create records in Route 53** and wait for the status to become *Issued*.
3. On GitHub, create the `DOMINIO` and `CERTIFICADO_ARN` variables in the `producao` environment and run the deploy again.
4. Back in Route 53, in the domain's zone, create four records: **A** and **AAAA** for the apex domain and for `www`, all as *Alias* to the CloudFront distribution.

Requests to `www` are redirected to the domain without www by CloudFront itself.

## 7. Database changes

Aurora DSQL doesn't run every kind of schema change PostgreSQL does. Keep new migrations **additive**:

- New fields: `null=True` (or keep them nullable and fill them in a later step). New foreign keys must be nullable.
- Don't change a column's type or `max_length` on an existing table, and don't drop columns: add a new field, copy the data, and stop using the old one.
- Data migrations change at most 3,000 rows per transaction; split bigger ones.

CI checks this on every push: the **Migrations on Aurora DSQL** step applies every migration through the DSQL engine and runs AWS's `dsql-lint` on the SQL. To run it on your computer, point a hostname at your local PostgreSQL (it must accept any password, `trust`) and run:

```bash
echo "127.0.0.1 ensaio.dsql.us-east-1.on.aws" | sudo tee -a /etc/hosts
createdb ensaio
DSQL_ENDPOINT=ensaio.dsql.us-east-1.on.aws DSQL_USER=$USER DSQL_DBNAME=ensaio DSQL_SSLMODE=disable \
  AWS_ACCESS_KEY_ID=x AWS_SECRET_ACCESS_KEY=x python manage.py ensaio_dsql | dsql-lint -
```

After upgrading Django or django-allauth, run `python -m pytest tests/test_dsql.py`. If it fails, the upgrade brought a new migration: run `python manage.py migracoes_dsql` to rebuild `config/migracoes/` and check whether the new schema change is something DSQL supports.

## 8. Backup and restore

- **Every day at 03:30** AWS Backup takes a snapshot of the database and keeps it for 30 days (AWS Backup → Backup vaults → `arcana-prod`).
- **Photos** are versioned on S3: a deleted or replaced photo can be recovered for 30 days (S3 → bucket → *Show versions*).

**Restoring the database.** A restore always creates a *new* cluster; the current one is left as it is:

1. AWS Backup → **Protected resources** → the Aurora DSQL cluster → pick a recovery point → **Restore**. Wait for the new cluster to become *Active* and copy its identifier.
2. Check it before switching: run `python manage.py shell` with `DSQL_ENDPOINT=<identifier>.dsql.sa-east-1.on.aws`, the same way as in step 5, and look at the latest orders.
3. To switch the site over, create the `BANCO_RESTAURADO` variable in the GitHub `producao` environment with the identifier and run the deploy. The Lambda and the daily backup move to the restored cluster.
4. Once everything is fine, delete the old cluster in the Aurora DSQL console (turn off deletion protection first).

**Rehearse this once a month.** A backup that has never been restored isn't a backup.

## 9. Monitoring and updates

- **Publishing:** merge into `main`. To roll back, revert the commit (`git revert`) and merge again.
- **Logs:** CloudWatch → Log groups → `/aws/lambda/arcana-prod-site` (kept for 14 days).
- **Uptime:** add `https://yourdomain/healthz/?banco=1` to UptimeRobot with a **5 minute** interval. Aurora DSQL doesn't sleep, so frequent checks cost almost nothing.
- **Costs:** Billing → *Bills* shows the current month per service, and the US$ 1 alert warns you if anything gets out of hand.

## 10. Limits of this architecture

- **Slower first visit.** After a while idle, the first request pays the Lambda cold start (1 to 3 s). An EventBridge schedule calls the Lambda every 5 minutes to keep it warm, for free and without touching the database. Aurora DSQL itself has no cold start.
- **Uploads up to 6 MB per request** (Lambda function URL limit). Resize photos before uploading them in the admin. Product videos bigger than that will need direct upload to S3, planned for a later phase.
- **Aurora DSQL free tier:** 100,000 DPUs and 1 GB of storage a month. Above that it's billed per use, with no instance to resize.
- **The Lambda connects as the database `admin`.** Fine for a single store; a dedicated database role with fewer permissions is a later improvement.

## Tearing down

```bash
aws cloudformation delete-stack --region sa-east-1 --stack-name arcana-prod
```

The photos bucket, the Aurora DSQL cluster (with deletion protection) and the backup vault are kept on purpose (`DeletionPolicy: Retain`). Delete them by hand in the console if you really want to remove everything: turn off the cluster's deletion protection, delete the vault's recovery points, then the resources.
