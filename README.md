# Arcana Crochet

Loja virtual da Arcana Crochet: peças de crochê feitas à mão, vendidas direto ao cliente.

**Stack:** Django 6.1 · PostgreSQL (Neon) · HTMX + Tailwind · AWS Lambda + CloudFront + S3 (infra em SAM, deploy pelo GitHub Actions com OIDC) · Docker Compose no desenvolvimento · Asaas (pagamentos) · Melhor Envio (frete).

A especificação técnica completa (modelo de dados, fluxos, segurança e LGPD) está no documento do projeto no Claude.

## Rodando no seu computador

### Opção A — com Docker (recomendado)

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
cp .env.example .env          # no Windows: copy .env.example .env
docker compose up --build     # sobe o banco e o site
```

Em outro terminal, crie seu usuário administrador:

```bash
docker compose exec web python manage.py createsuperuser
```

- Loja: http://localhost:8000
- Painel: http://localhost:8000/admin/
- E-mails (confirmação de cadastro, senha) aparecem no terminal do `docker compose`.

### Opção B — sem Docker

Pré-requisitos: Python 3.13 e PostgreSQL rodando localmente.

```bash
python -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements/dev.txt
cp .env.example .env             # ajuste DATABASE_URL para o seu Postgres
# usuário e banco esperados pelo .env (rode no psql como postgres):
#   CREATE USER arcana WITH PASSWORD 'arcana' CREATEDB; CREATE DATABASE arcana OWNER arcana;
python manage.py migrate
python manage.py createsuperuser
python manage.py popular_demo    # opcional: peças, pedidos e avaliações de exemplo
python manage.py runserver
```

## Comandos do dia a dia

| O que | Comando |
| --- | --- |
| Rodar os testes | `python -m pytest` |
| Verificar estilo | `ruff check .` e `ruff format .` |
| Criar migrações | `python manage.py makemigrations` |
| Aplicar migrações | `python manage.py migrate` |
| Dados de exemplo | `python manage.py popular_demo` (cliente: `cliente@arcana.test` / `arcana-demo-123`) |
| CSS (Tailwind) | `npm install` uma vez, depois `npm run watch:css` ou `npm run build:css` |

Com Docker, prefixe com `docker compose exec web`, por exemplo `docker compose exec web python -m pytest`.

## Estrutura

```
config/            configurações do Django, URLs e leitura de segredos do SSM
apps/core/         base comum: ModeloBase (UUID v7), preços (Pix e parcelas), filtros de template
apps/contas/       usuário com login por e-mail, papéis cliente/atendente/admin, endereços
apps/catalogo/     categorias, produtos, variações, fotos, ficha técnica, estoque, busca e filtros
apps/pedidos/      sacola, frete, cupons, checkout, pedidos e acompanhamento
apps/avaliacoes/   avaliações de quem recebeu a peça, com moderação
templates/         páginas da loja (home, listagem, produto, sacola, checkout, minha conta)
static/            CSS compilado, JS da loja, fontes e imagens da marca
docker/            Dockerfile (o mesmo para desenvolvimento e Lambda) e entrypoint
infra/             AWS: template SAM da loja, base (ECR + papel do GitHub) e script de segredos
frontend/          fonte do Tailwind (compila para static/css/app.css)
docs/              guias de frontend, deploy na AWS e contas externas
tests/             testes automatizados (pytest)
```

## Regras importantes do código

- **Dinheiro em centavos** (`BigIntegerField`). Para exibir, use o filtro `{{ valor|brl }}`.
- **Estoque só muda por `registrar_movimentacao`** (`apps/catalogo/estoque.py`). Pelo painel, registre uma *movimentação de estoque*; o campo de estoque é somente leitura.
- **Equipe da loja:** crie o usuário no painel com papel *Atendente* e adicione-o ao grupo *Atendimento*. MFA fica em `/conta/2fa/`.

## Git

- `dev`: desenvolvimento do dia a dia. O CI roda a cada push.
- `main`: o que está em produção. Só recebe merge de `dev` testado, e cada merge publica na AWS.

## Roadmap

- [x] **Fundação:** projeto Django, Docker, CI, cadastro e login por e-mail com verificação
- [x] **Catálogo (base):** modelos de produto, variação, foto e estoque; painel; vitrine e página de produto
- [x] **Frontend da loja:** home, listagem com filtros, produto, sacola, checkout em etapas, acompanhamento do pedido ([docs/frontend.md](docs/frontend.md))
- [x] **Hospedagem:** AWS Lambda + CloudFront + S3, banco no Neon, deploy e backup automáticos ([docs/deploy.md](docs/deploy.md))
- [ ] **Transação:** cotação no Melhor Envio, Pix e cartão no Asaas, webhooks, etiqueta, e-mails do pedido, upload direto para o S3
- [ ] **Pós-venda:** atendimento, trocas e devoluções, relatórios
- [ ] **Lançamento:** textos legais, teste de segurança, backup testado, beta com clientes

Guias: [frontend](docs/frontend.md) · [deploy na AWS](docs/deploy.md) · [contas externas e formalização](docs/contas-externas.md)
