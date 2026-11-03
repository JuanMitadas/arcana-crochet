# Contas externas e formalização

Ordem sugerida: sandboxes primeiro (gratuitas, destravam o desenvolvimento), formalização em paralelo, contas de produção só perto do lançamento.

## 1. Formalização (MEI)

Crochê pode ser MEI: a ocupação é **crocheteiro(a) independente**, CNAE 1422-3/00. Em 2026 o DAS fica em torno de R$ 82/mês e o limite de faturamento é R$ 81 mil/ano.

1. Crie ou recupere sua conta **gov.br** (nível prata ou ouro).
2. Abra o MEI pelo Portal do Empreendedor, escolhendo a ocupação acima.
3. Antes de vender, leve estas perguntas a um contador:
   - A atividade exige **Inscrição Estadual** em SP? (é atividade industrial e paga ICMS no DAS)
   - Os envios pelos Correios/transportadoras precisam de **NF-e**, ou posso usar declaração de conteúdo? O Melhor Envio só aceita declaração para pessoa física e PJ **não** contribuinte de ICMS.
   - Como emitir NF-e quando necessário (emissor gratuito da SEFAZ ou um ERP)?
   - O site em nome do MEI pode ter domínio e conta PJ no Asaas e no Melhor Envio sem problema?

## 2. Asaas — sandbox (pagamentos)

1. Crie uma conta em **https://sandbox.asaas.com** (é separada da conta real; pode usar dados fictícios de teste).
2. No menu, abra **Integrações** e gere a **chave de API**. Ela aparece **uma única vez**: copie na hora.
3. No `.env`, preencha:
   ```
   ASAAS_BASE_URL=https://sandbox.asaas.com/api/v3
   ASAAS_API_KEY=<a chave copiada>
   ```
4. A chave vai no cabeçalho `access_token` das requisições, junto com `User-Agent` (a integração do projeto fará isso).
5. Webhook: só na fase de transação. Precisará de uma URL pública: o site já publicado na AWS (endereço do CloudFront ou o domínio próprio).

Documentação: https://docs.asaas.com (seções Sandbox, Cobranças, Pix, Webhooks).

## 3. Melhor Envio — sandbox (frete)

1. Crie uma conta em **https://sandbox.melhorenvio.com.br**. O sandbox já começa com R$ 10.000 fictícios para gerar etiquetas de teste.
2. Cadastre o endereço de origem da loja (de onde as peças sairão).
3. Gere um token de acesso no painel (área de **Integrações** → tokens/permissões de acesso). Para uma loja única, o token pessoal da própria conta é suficiente; o fluxo OAuth com aplicativo (Integrações → Área Dev → Cadastrar aplicativo) só é necessário se outras contas fossem usar o sistema.
4. No `.env`, preencha:
   ```
   MELHOR_ENVIO_BASE_URL=https://sandbox.melhorenvio.com.br
   MELHOR_ENVIO_TOKEN=<o token>
   MELHOR_ENVIO_USER_AGENT=Arcana Crochet (seu-email@exemplo.com)
   ```
5. Toda requisição precisa do cabeçalho `User-Agent` no formato `Nome do app (email)`.

Documentação: https://docs.melhorenvio.com.br

## 4. AWS, Neon e domínio

O passo a passo completo (conta AWS, banco no Neon, segredos, deploy pelo GitHub e domínio próprio) está em [deploy.md](deploy.md).

Domínio: registre o `.com.br` no **Registro.br** (precisa de CPF ou CNPJ). Dá para publicar e testar antes, no endereço `*.cloudfront.net`.

## 5. E-mail transacional

Sem e-mail configurado, ninguém consegue criar conta na loja publicada (o cadastro exige confirmar o e-mail). Crie uma conta no **Resend** ou no **Brevo**, verifique o domínio (eles mostram os registros SPF/DKIM para colar no DNS) e grave a credencial SMTP no parâmetro `EMAIL_URL` com `infra/configurar-segredos.sh`:

```
EMAIL_URL=smtp+tls://<usuario>:<senha-ou-api-key>@<servidor-smtp>:587
```

## 6. Contas de produção (perto do lançamento)

Com o CNPJ em mãos: conta **PJ** no Asaas (`https://api.asaas.com/v3`) e no Melhor Envio (`https://melhorenvio.com.br`), com saldo para etiquetas. Troque as URLs e chaves nos parâmetros do SSM (`/arcana/prod/`). Nunca use chave de produção no `.env` do seu computador.
