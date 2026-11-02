# Deploy no VPS

Guia para colocar a loja no ar num VPS (ex.: Hostinger KVM 2 em São Paulo, Ubuntu 24.04) atrás da Cloudflare. Faça uma vez, com calma; depois cada atualização é um `git pull` + `docker compose up`.

## 1. Servidor

No painel da Hostinger, crie o VPS com **Ubuntu 24.04** no datacenter de **São Paulo** e cadastre sua **chave SSH pública** (não use senha).

Entre como root e crie um usuário próprio:

```bash
ssh root@IP_DO_VPS
adduser arcana && usermod -aG sudo arcana
rsync --archive --chown=arcana:arcana ~/.ssh /home/arcana
```

Endureça o SSH e o sistema (ainda como root):

```bash
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
apt update && apt upgrade -y
apt install -y fail2ban unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

Teste `ssh arcana@IP_DO_VPS` **em outro terminal** antes de fechar a sessão de root.

## 2. Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker arcana   # saia e entre de novo no SSH
```

## 3. Firewall: só a Cloudflare chega no servidor

> **Atenção:** o Docker abre as portas publicadas direto no iptables e **ignora o `ufw`**. Por isso o bloqueio das portas 80/443 deve ser feito no **firewall do painel da Hostinger** (VPS → Firewall), não só no `ufw`.

No firewall do painel, crie regras:

- **SSH (22):** permitir só do seu IP (ou de qualquer lugar, se o seu IP muda; o login por senha já está desligado).
- **HTTPS (443) e HTTP (80):** permitir só das faixas de IP da Cloudflare, listadas em https://www.cloudflare.com/ips-v4 e https://www.cloudflare.com/ips-v6.
- Negar o resto.

Só depois disso é seguro usar `TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP` no `.env.prod`.

## 4. Cloudflare

1. **DNS:** registros `A` para `@` e `www` apontando para o IP do VPS, com a nuvem laranja (proxy) **ligada**.
2. **SSL/TLS:** modo **Full (strict)**.
3. **SSL/TLS → Origin Server → Create Certificate** (validade de 15 anos). Salve o certificado e a chave no VPS:
   ```bash
   mkdir -p ~/arcana-crochet/certs
   nano ~/arcana-crochet/certs/origin.pem       # cole o certificado
   nano ~/arcana-crochet/certs/origin-key.pem   # cole a chave privada
   chmod 600 ~/arcana-crochet/certs/*.pem
   ```
4. **Zero Trust → Access:** crie uma aplicação para `seudominio.com.br/<ADMIN_URL>` liberando só o seu e-mail. O painel passa a exigir login da Cloudflare antes do login do Django.

## 5. Subir a aplicação

```bash
git clone https://github.com/JuanMitadas/arcana-crochet.git ~/arcana-crochet
cd ~/arcana-crochet
git checkout main
cp .env.example .env.prod
nano .env.prod     # use o bloco "Exemplo de .env.prod" do próprio arquivo
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

Confira: `https://seudominio.com.br/healthz/` deve responder `{"status": "ok"}`.

## 6. Atualizar

```bash
cd ~/arcana-crochet
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

As migrações rodam sozinhas quando o container `web` sobe.

## 7. Backup (mínimo para começar)

Até o WAL-G entrar no roadmap, faça um dump diário enviado para o R2 com o `rclone`:

```bash
sudo apt install -y rclone
rclone config   # crie um remoto "r2" do tipo S3 / Cloudflare com a chave do R2
crontab -e
```

Linha do cron (todo dia às 3h):

```
0 3 * * * cd ~/arcana-crochet && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U arcana -Fc arcana > /tmp/arcana.dump && rclone copy /tmp/arcana.dump r2:arcana-backups/$(date +\%F)/ && rm /tmp/arcana.dump
```

**Teste a restauração** uma vez por mês num banco vazio (`pg_restore`). Backup que nunca foi restaurado não é backup.

## 8. Monitoramento

- **Uptime:** cadastre `https://seudominio.com.br/healthz/` num monitor gratuito (UptimeRobot ou Better Stack) com alerta por e-mail.
- **Erros:** crie um projeto gratuito no Sentry; a integração com o Django entra numa próxima etapa.
